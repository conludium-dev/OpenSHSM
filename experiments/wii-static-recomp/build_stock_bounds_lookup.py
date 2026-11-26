"""Derive disjoint first-match ranges from the actual master; retain its O0/setjmp wrapper."""
from pathlib import Path
import hashlib
import heapq
import json
import re
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-bounds-lookup'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-cpu-time/build.json'
parent = json.loads(parent_path.read_text())
for path, digest in {**parent['dependencies'], **parent['retainedInputs']}.items():
    assert sha(Path(path)) == digest
command = list(parent['linkCommand'])
old_master = next(Path(arg) for arg in command if Path(arg).name == 'fixed.cpp.o')
original = old_master.with_suffix('')
text = original.read_text()
table = text.split('static const FuncBound g_func_bounds[] = {', 1)[1].split('};', 1)[0]
records = []
sentinel = False
for line in table.splitlines():
    if not line.strip():
        continue
    match = re.fullmatch(r'\s*\{(0x[0-9A-Fa-f]+|0), (0x[0-9A-Fa-f]+|0), (func_[0-9A-Fa-f]+|nullptr)\},?\s*', line)
    assert match, line
    start, end = (int(match[i], 0) for i in (1, 2))
    if start == 0:
        sentinel = True
        break
    assert start < end <= 0xFFFFFFFF
    records.append((start, end, match[3]))
assert records and sentinel
events = {}
for index, (start, end, _) in enumerate(records):
    events.setdefault(start, []).append(index)
    events.setdefault(end, [])
points = sorted(events)
active = []
ranges = []
for point, following in zip(points, points[1:]):
    for index in events[point]:
        heapq.heappush(active, index)
    while active and records[active[0]][1] <= point:
        heapq.heappop(active)
    if not active:
        continue
    index = active[0]
    if ranges and ranges[-1][1] == point and ranges[-1][2] == index:
        ranges[-1] = (ranges[-1][0], following, index)
    else:
        ranges.append((point, following, index))
assert ranges
header = output / 'stock_bounds_lookup.h'
header.write_bytes((public / header.name).read_bytes())
lookup_source = output / 'bounds.cpp'
lookup_source.write_text('#include "stock_bounds_lookup.h"\nstatic const StockBoundsRange ranges[] = {\n' +
    ''.join(f'    {{0x{start:08X}, 0x{end:08X}, {index}}},\n' for start, end, index in ranges) +
    '};\nextern "C" uint32_t stock_lookup_bounds(uint32_t target) {\n'
    '    return stock_bounds_index(ranges, sizeof(ranges) / sizeof(ranges[0]), target);\n}\n')
start = text.index('extern "C" void run_game(')
end = text.index('\nextern "C" int sdk_enable_route', start)
body = text[start:end]
before = '''                for (const auto& fb : g_func_bounds) {
                    if (fb.start == 0) break;
                    if (target >= fb.start && target < fb.end) {
                        ctx.pc = target;
                        fb.func(ctx);
                        found = true;
                        break;
                    }
                }'''
after = '''                uint32_t bound_index = stock_lookup_bounds(target);
                if (bound_index != UINT32_MAX) {
                    const auto& fb = g_func_bounds[bound_index];
                    ctx.pc = target;
                    fb.func(ctx);
                    found = true;
                }'''
assert body.count(before) == 1
declaration = 'extern "C" uint32_t stock_lookup_bounds(uint32_t target);\n\n'
master_source = output / 'fixed.cpp'
master_source.write_text(text[:start] + declaration + body.replace(before, after, 1) + text[end:])
record = json.loads((root / 'window-sdk-enable-resume/build.json').read_text())
arguments = record.get('arguments')
if arguments is None:
    arguments = json.loads((root / 'window-fp-guard/output_37.cpp.record.json').read_text())['arguments']
compiler = '/Library/Developer/CommandLineTools/usr/bin/c++'
sdk = arguments[arguments.index('-isysroot') + 1]
master_obj, lookup_obj = output / 'fixed.cpp.o', output / 'bounds.cpp.o'
for label, compile_command in [
    ('lookup', [compiler, '-isysroot', sdk, '-std=c++20', '-O2', '-c', str(lookup_source), '-o', str(lookup_obj)]),
    ('master', [compiler, *arguments, '-I', str(original.parent), '-c', str(master_source), '-o', str(master_obj)])]:
    result = subprocess.run(compile_command, capture_output=True, text=True, timeout=180)
    (output / f'{label}-compile.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-2500:]
command[command.index(str(old_master))] = str(master_obj)
command.insert(1, str(lookup_obj))
exe = output / 'OpenSHSMStockBoundsLookup'
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2500:]
inputs = {}
for arg in command:
    if Path(arg).suffix in ('.o', '.a') and arg not in (str(master_obj), str(lookup_obj)):
        path = (Path(arg) if Path(arg).is_absolute() else root / 'export/build' / arg).resolve()
        inputs[str(path)] = sha(path)
(output / 'build.json').write_text(json.dumps({
    'result': 'FIRST_MATCH_BOUNDS_LOOKUP_BUILT_UNVERIFIED', 'parentBuildSha256': sha(parent_path),
    'masterOriginalPath': str(original), 'masterOriginalSha256': sha(original),
    'masterSourceSha256': sha(master_source), 'masterObjectSha256': sha(master_obj),
    'lookupSourceSha256': sha(lookup_source), 'lookupObjectSha256': sha(lookup_obj),
    'masterPatch': [before, after], 'declaration': declaration,
    'sdk': sdk,
    'records': records, 'ranges': ranges, 'linkCommand': command,
    'executableSha256': sha(exe), 'retainedInputs': inputs,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), public / header.name, header]},
    'limits': ['Host routing adaptation, not recovered Wii behavior.',
        'Only run_game bounds fallback replaced; original table/exact routes/SDK dispatch/setjmp remain.',
        'Static disjoint ranges preserve earliest original overlapping record; verification pending.',
        'No counters, no guest/runtime/main/audio/clock changes; existing movie CPU-time observer retained.']}, indent=2) + '\n')
print('FIRST_MATCH_BOUNDS_LOOKUP_BUILT_UNVERIFIED', len(records), len(ranges))

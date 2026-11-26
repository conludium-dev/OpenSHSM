"""Count only actual run_game routing branches; keep O0/setjmp and all original state handling."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-dispatch-counts'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-cpu-time/build.json'
parent = json.loads(parent_path.read_text())
for path, digest in {**parent['dependencies'], **parent['retainedInputs']}.items():
    assert sha(Path(path)) == digest
command = list(parent['linkCommand'])
old_master = next(Path(arg) for arg in command if Path(arg).name == 'fixed.cpp.o')
master_original = old_master.with_suffix('')
text = master_original.read_text()
start = text.index('extern "C" void run_game(')
end = text.index('\nextern "C" int sdk_enable_route', start)
body = text[start:end]
patches = [
    ('if (auto function = lookup_dispatch(target)) {\n            function(ctx);',
     'if (auto function = lookup_dispatch(target)) {\n            ++stock_dispatch_counts[0];\n            function(ctx);'),
    ('for (const auto& fb : g_func_bounds) {', 'for (const auto& fb : g_func_bounds) {\n                    ++stock_dispatch_counts[3];'),
    ('                        ctx.pc = target;\n                        fb.func(ctx);',
     '                        ++stock_dispatch_counts[1];\n                        ctx.pc = target;\n                        fb.func(ctx);'),
    ('                    nwii::runtime::interpret_step(ctx);',
     '                    ++stock_dispatch_counts[2];\n                    nwii::runtime::interpret_step(ctx);'),
    ('      } else {\n          continue;', '      } else {\n          ++stock_dispatch_counts[4];\n          continue;')]
for before, after in patches:
    assert body.count(before) == 1
    body = body.replace(before, after)
helper = '''static uint64_t stock_dispatch_counts[5]{};
extern "C" void stock_dispatch_snapshot(uint64_t* values) {
    for (unsigned i = 0; i < 5; ++i) { values[i] = stock_dispatch_counts[i]; }
}

'''
master_source, master_obj = output / 'fixed.cpp', output / 'fixed.cpp.o'
master_source.write_text(text[:start] + helper + body + text[end:])
record = json.loads((root / 'window-sdk-enable-resume/build.json').read_text())
arguments = record.get('arguments')
if arguments is None:
    arguments = json.loads((root / 'window-fp-guard/output_37.cpp.record.json').read_text())['arguments']
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-I', str(master_original.parent), '-c', str(master_source), '-o', str(master_obj)],
    capture_output=True, text=True, timeout=180)
(output / 'master-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2500:]
header_original = root / 'window-cpu-time/stock_movie_timing.h'
header_text = header_original.read_text()
header_patches = [('#include <time.h>', '#include <time.h>\nextern "C" void stock_dispatch_snapshot(uint64_t*);'),
    ('    timespec cpu_time{};', '    uint64_t dispatch[5]{};\n    stock_dispatch_snapshot(dispatch);\n    timespec cpu_time{};'),
    ('\\"r3\\":%u,\\"r4\\":%u,\\"r5\\":%u,\\"r6\\":%u}\\n',
     '\\"r3\\":%u,\\"r4\\":%u,\\"r5\\":%u,\\"r6\\":%u,\\"exact\\":%llu,\\"bounds\\":%llu,\\"interpreter\\":%llu,\\"boundsIterations\\":%llu,\\"exceptions\\":%llu}\\n'),
    ('ctx.gpr[3], ctx.gpr[4], ctx.gpr[5], ctx.gpr[6]);',
     'ctx.gpr[3], ctx.gpr[4], ctx.gpr[5], ctx.gpr[6],\n'
     '        (unsigned long long)dispatch[0], (unsigned long long)dispatch[1], (unsigned long long)dispatch[2],\n'
     '        (unsigned long long)dispatch[3], (unsigned long long)dispatch[4]);')]
for before, after in header_patches:
    assert header_text.count(before) == 1
    header_text = header_text.replace(before, after)
header = output / 'stock_movie_timing.h'
header.write_text(header_text)
guard = output / 'constant_fp_guard.h'
guard.write_bytes((root / 'window-cpu-time/constant_fp_guard.h').read_bytes())
changes = {}
for unit in (11, 37):
    old = next(Path(arg) for arg in command if Path(arg).name == f'output_{unit}.cpp.o')
    original = old.with_suffix('')
    source, obj = output / original.name, output / old.name
    source.write_bytes(original.read_bytes())
    flags = parent['changes'][str(unit)]['arguments']
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *flags,
        '-I', str(original.parent), '-I', str(root / 'headless-psq-scale'),
        '-I', str(root / 'window-movie-dma'), '-c', str(source), '-o', str(obj)],
        capture_output=True, text=True, timeout=180)
    (output / f'compile-{unit}.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-2500:]
    command[command.index(str(old))] = str(obj)
    changes[str(unit)] = {'originalPath': str(original), 'originalSha256': sha(original),
        'sourceSha256': sha(source), 'objectSha256': sha(obj)}
command[command.index(str(old_master))] = str(master_obj)
exe = output / 'OpenSHSMStockDispatchCounts'
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2500:]
inputs = {}
for arg in command:
    if Path(arg).suffix in ('.o', '.a') and arg not in [str(master_obj), *[str(output / f'output_{u}.cpp.o') for u in (11, 37)]]:
        path = (Path(arg) if Path(arg).is_absolute() else root / 'export/build' / arg).resolve()
        inputs[str(path)] = sha(path)
(output / 'build.json').write_text(json.dumps({'result': 'MASTER_BRANCH_COUNTS_BUILT_LIVE_UNVERIFIED',
    'parentBuildSha256': sha(parent_path), 'changes': changes, 'masterOriginalPath': str(master_original),
    'masterOriginalSha256': sha(master_original), 'masterSourceSha256': sha(master_source),
    'masterObjectSha256': sha(master_obj), 'masterPatches': patches, 'masterHelper': helper,
    'headerPatches': header_patches, 'linkCommand': command, 'executableSha256': sha(exe),
    'retainedInputs': inputs, 'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), header_original, header, guard]},
    'limits': ['Counters apply only actual run_game exact/bounds/interpreter/nonlocal-exception branches, not nested guest interpreter calls.',
        'Same CPU host thread and existing movie observer, no registry/runtime/service/queue/clock change.',
        'O0/setjmp/source state restored mechanically; boundsIterations is visited records including sentinel, not machine instructions.']}, indent=2) + '\n')
print('MASTER_BRANCH_COUNTS_BUILT_LIVE_UNVERIFIED')

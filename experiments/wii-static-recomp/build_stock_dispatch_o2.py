"""Optimize only exact-index selection over the unchanged authoritative route array, retaining O0 master."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-dispatch-o2'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-scheduler-o2/build.json'
parent = json.loads(parent_path.read_text())
component_path = root / 'window-scheduler-o2/component-verification.json'
component = json.loads(component_path.read_text())
assert component['result'] == 'SCHEDULER_O2_CONTRACT_CALLBACK4_SDK7_SC3_LATE18_EQUAL'
assert component['buildSha256'] == sha(parent_path)
for path, digest in {**parent['dependencies'], **parent['retainedInputs']}.items():
    assert sha(Path(path)) == digest
command = list(parent['linkCommand'])
old_master = next(Path(arg) for arg in command if Path(arg).name == 'fixed.cpp.o')
original = old_master.with_suffix('')
prior_path = root / 'window-bounds-lookup/build.json'
prior = json.loads(prior_path.read_text())
assert sha(original) == prior['masterSourceSha256']
assert sha(old_master) == prior['masterObjectSha256']
text = original.read_text()
table = text.split('static const DispatchRoute g_dispatch_routes[] = {', 1)[1].split('};', 1)[0]
records = []
for line in table.splitlines():
    if not line.strip():
        continue
    match = re.fullmatch(r'\s*\{(0x[0-9A-Fa-f]+), ([A-Za-z_]\w*)\},?\s*', line)
    assert match, line
    records.append([int(match[1], 16), match[2]])
assert records and all(a[0] <= b[0] for a, b in zip(records, records[1:]))
before_struct = 'struct DispatchRoute { uint32_t address; void(*function)(CPUContext&); };'
after_struct = 'using DispatchRoute = StockDispatchRoute;'
start = text.index('static void(*lookup_dispatch(uint32_t target))(CPUContext&) {')
end = text.index('\n// --- Entry Point Wrapper ---', start)
before = text[start:end]
after = '''static void(*lookup_dispatch(uint32_t target))(CPUContext&) {
    const size_t count = sizeof(g_dispatch_routes) / sizeof(g_dispatch_routes[0]);
    const size_t index = stock_dispatch_index(g_dispatch_routes, count, target);
    return index < count ? g_dispatch_routes[index].function : nullptr;
}
'''
patches = [[before_struct, after_struct], [before, after]]
for old, new in patches:
    assert text.count(old) == 1
    text = text.replace(old, new, 1)
text = '#include "stock_dispatch_lookup.h"\n' + text
cache = Path(tempfile.mkdtemp(prefix='openshsm-dispatch-o2-', dir='/private/tmp'))
source, master_obj, helper_obj = cache / 'fixed.cpp', cache / 'fixed.cpp.o', cache / 'dispatch.cpp.o'
source.write_text(text)
master_record = json.loads((root / 'window-sdk-enable-resume/build.json').read_text())
arguments = master_record.get('arguments')
if arguments is None:
    arguments = json.loads((root / 'window-fp-guard/output_37.cpp.record.json').read_text())['arguments']
assert '#pragma clang optimize off' in text and '#pragma GCC optimize ("O0")' in text
sdk = arguments[arguments.index('-isysroot') + 1]
commands = [
    ['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments, '-I', str(public),
        '-I', str(original.parent), '-c', str(source), '-o', str(master_obj)],
    ['/Library/Developer/CommandLineTools/usr/bin/c++', '-isysroot', sdk, '-std=c++20', '-O2',
        '-c', str(public / 'stock_dispatch_lookup.cpp'), '-o', str(helper_obj)]]
for label, compile_command in zip(('master', 'helper'), commands):
    result = subprocess.run(compile_command, capture_output=True, text=True, timeout=180)
    (output / f'{label}-compile.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-2500:]
command[command.index(str(old_master))] = str(master_obj)
command.insert(1, str(helper_obj))
exe = cache / 'OpenSHSMStockDispatchO2'
command[command.index('-o') + 1] = str(exe)
linked = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(linked.stdout + linked.stderr)
assert linked.returncode == 0, linked.stderr[-2500:]
retained = {}
for arg in command:
    if Path(arg).suffix in ('.o', '.a') and arg not in (str(master_obj), str(helper_obj)):
        path = (Path(arg) if Path(arg).is_absolute() else root / 'export/build' / arg).resolve()
        retained[str(path)] = sha(path)
(output / 'build.json').write_text(json.dumps({
    'result': 'AUTHORITATIVE_EXACT_DISPATCH_HELPER_O2_BUILT_UNVERIFIED', 'parentBuildSha256': sha(parent_path),
    'parentComponentSha256': sha(component_path), 'masterOriginalPath': str(original),
    'masterOriginalSha256': sha(original), 'masterSourcePath': str(source), 'masterSourceSha256': sha(source),
    'masterObjectPath': str(master_obj), 'masterObjectSha256': sha(master_obj),
    'helperObjectPath': str(helper_obj), 'helperObjectSha256': sha(helper_obj),
    'masterPatches': patches, 'includeAddition': '#include "stock_dispatch_lookup.h"\n',
    'routeRecords': records, 'compileCommands': commands, 'linkCommand': command,
    'executablePath': str(exe), 'executableSha256': sha(exe), 'retainedInputs': retained,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), source,
        public / 'stock_dispatch_lookup.h', public / 'stock_dispatch_lookup.cpp']},
    'limits': ['Pure lower_bound exact-index helper over original route array; duplicates retain first match; no new table/cache/service.',
        'Master inherited flags retained (includeO2), explicit clang optimize-off/GCC O0 pragmas retained; setjmp/run_game/SDK bodies unchanged.',
        'All75guests/runtime/archive/main/audio/clock/IRQ/waits/current bounds helper retained.',
        'Native adapter, not original Wii dispatch logic; equivalence/callback/frame/live proof pending.',
        'Large generated master/source/object/executable temporary cache; small manifest on Data.']}, indent=2) + '\n')
print('AUTHORITATIVE_EXACT_DISPATCH_HELPER_O2_BUILT_UNVERIFIED', len(records), exe)

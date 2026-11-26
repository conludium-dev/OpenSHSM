"""Replace only the pure exact-index helper in the correct-cadence candidate."""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-vi-busy-latch/build.json'
parent = json.loads(parent_path.read_text())
component_path = parent_path.parent / 'component-verification.json'
component = json.loads(component_path.read_text())
assert component['result'] == 'VI_BUSY_LATCH_DEC9_CALLBACK4_SDK7_SC3_LATE18_EQUAL'
assert component['buildSha256'] == sha(parent_path)
for path, digest in {**parent['dependencies'], **parent['retainedInputs']}.items():
    assert sha(Path(path)) == digest
proof_path = root / 'dispatch-select-proof/verification.json'
proof = json.loads(proof_path.read_text())
original = public / 'stock_dispatch_select.cpp'
assert sha(original) == proof['sourceSha256']
assert sha(public / 'stock_dispatch_select_probe.cpp') == proof['probeSha256']
route_path = root / 'window-dispatch-o2/build.json'
route = json.loads(route_path.read_text())
old = Path(route['helperObjectPath'])
assert sha(old) == route['helperObjectSha256'] == proof['baselineObjectSha256']
cache = Path(tempfile.mkdtemp(prefix='openshsm-dispatch-select-link-', dir='/private/tmp'))
source, obj = cache / 'dispatch.cpp', cache / 'dispatch.cpp.o'
before, after = 'stock_dispatch_select_index', 'stock_dispatch_index'
text = original.read_text()
assert text.count(before) == 1
source.write_text(text.replace(before, after, 1))
assert source.read_text().replace(after, before, 1) == text
command = list(route['compileCommands'][1])
command[command.index('-c') + 1] = str(source)
command[command.index('-o') + 1] = str(obj)
command.extend(['-I', str(public)])
compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
assert compiled.returncode == 0, compiled.stderr[-3000:]
link = list(parent['linkCommand'])
assert link.count(str(old)) == 1
link[link.index(str(old))] = str(obj)
exe = cache / 'OpenSHSMStockDispatchSelect'
link[link.index('-o') + 1] = str(exe)
linked = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert linked.returncode == 0, linked.stderr[-3000:]
retained = {}
for arg in link:
    if Path(arg).suffix in ('.o', '.a') and arg != str(obj):
        path = (Path(arg) if Path(arg).is_absolute() else root / 'export/build' / arg).resolve()
        retained[str(path)] = sha(path)
output = root / 'window-dispatch-select'
output.mkdir(exist_ok=True)
(output / 'build.json').write_text(json.dumps({
    'result': 'PURE_EXACT_SELECT_HELPER_LINKED_UNVERIFIED', 'parentBuildSha256': sha(parent_path),
    'parentComponentSha256': sha(component_path), 'routeProofSha256': sha(proof_path),
    'sourcePath': str(source), 'sourceSha256': sha(source), 'originalSourcePath': str(original),
    'abiRename': [before, after], 'objectPath': str(obj), 'objectSha256': sha(obj),
    'originalObjectPath': str(old), 'compileCommand': command, 'linkCommand': link,
    'archivePath': parent['archivePath'], 'archiveSha256': parent['archiveSha256'],
    'executablePath': str(exe), 'executableSha256': sha(exe), 'retainedInputs': retained,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), original,
        source, public / 'stock_dispatch_lookup.h', proof_path]},
    'limits': ['Existing ABI pure helper only; original master/table/75guests/archive/VI/clock/audio retained.',
        'No second routing table/cache/service, no master optimization guard removal.',
        'Native callbacks/frames/timer and live cadence/performance acceptance pending; not promoted.']}, indent=2) + '\n')
print('PURE_EXACT_SELECT_HELPER_LINKED_UNVERIFIED', exe)

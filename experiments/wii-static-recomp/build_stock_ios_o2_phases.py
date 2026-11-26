"""Reuse the verified existing main/VI observer objects with the identical-source IOS O2 runtime."""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-ios-o2-phases'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-ios-o2/build.json'
phase_path = root / 'window-live-phases/build.json'
parent = json.loads(parent_path.read_text())
phase = json.loads(phase_path.read_text())
for record in (parent, phase):
    for path, digest in {**record['dependencies'], **record['retainedInputs']}.items():
        assert sha(Path(path)) == digest
component_path = root / 'window-ios-o2/component-verification.json'
component = json.loads(component_path.read_text())
assert component['buildSha256'] == sha(parent_path) and component['result'] == 'IOS_O2_CALLBACK4_FRAME3_SDK7_SC3_PASS'
command = list(parent['linkCommand'])
for name, prefix in [('main.cpp.o', 'main'), ('output_39.cpp.o', 'vi')]:
    old = next(Path(arg) for arg in command if Path(arg).name == name)
    original_source = old.with_suffix('')
    assert sha(original_source) == phase[prefix + 'OriginalSha256']
    replacement = root / 'window-live-phases' / name
    assert sha(replacement) == phase[prefix + 'ObjectSha256']
    assert sha(replacement.with_suffix('')) == phase[prefix + 'SourceSha256']
    command[command.index(str(old))] = str(replacement)
cache = Path(tempfile.mkdtemp(prefix='openshsm-ios-o2-phases-', dir='/private/tmp'))
exe = cache / 'OpenSHSMStockIOSO2Phases'
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2500:]
inputs = {}
for arg in command:
    if Path(arg).suffix in ('.o', '.a'):
        path = (Path(arg) if Path(arg).is_absolute() else root / 'export/build' / arg).resolve()
        inputs[str(path)] = sha(path)
(output / 'build.json').write_text(json.dumps({
    'result': 'IOS_O2_EXISTING_PHASES_RELINKED_UNVERIFIED', 'parentBuildSha256': sha(parent_path),
    'phaseBuildSha256': sha(phase_path), 'parentComponentSha256': sha(component_path),
    'executablePath': str(exe), 'executableSha256': sha(exe), 'linkCommand': command, 'retainedInputs': inputs,
    'dependencies': {str(Path(__file__).resolve()): sha(Path(__file__).resolve())},
    'limits': ['Existing exact observer main/VI objects reused, original source parents match current main/guest39.',
        'Current IOS-O2/all other74guests/master/audio/clock/sleep/IRQ policy retained; no new render or timer changes.',
        'Host phase timestamps include observer overhead; GX frequency not unique movie frame FPS.',
        'Large executable temporary Mac cache, other evidence/project/resources stay Data.',
        'Observation-only integration/source audit and bounded live phase profile pending.']}, indent=2) + '\n')
print('IOS_O2_EXISTING_PHASES_RELINKED_UNVERIFIED', exe)

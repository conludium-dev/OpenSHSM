"""Re-link existing verified timer-only main with current DEC/runtime and unchanged SDK observer."""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-current-vi-timer'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-dec-ee-gate/build.json'
parent = json.loads(parent_path.read_text())
component_path = parent_path.parent / 'component-verification.json'
component = json.loads(component_path.read_text())
assert component['result'] == 'DEC_EE_GATE_DEC9_CALLBACK4_SDK7_SC3_LATE18_EQUAL'
assert component['buildSha256'] == sha(parent_path)
for path, digest in {**parent['dependencies'], **parent['retainedInputs']}.items():
    assert sha(Path(path)) == digest
timer_path = root / 'window-vi-timer/build.json'
timer = json.loads(timer_path.read_text())
phase_path = root / 'window-live-phases/build.json'
phase = json.loads(phase_path.read_text())
assert timer['parentBuildSha256'] == sha(phase_path)
original = Path(timer['mainOriginalPath'])
assert sha(original) == timer['mainOriginalSha256'] == phase['mainSourceSha256']
timer_source, timer_obj = timer_path.parent / 'main.cpp', timer_path.parent / 'main.cpp.o'
assert sha(timer_source) == timer['sourceSha256'] and sha(timer_obj) == timer['objectSha256']
before, after = timer['patch']
assert original.read_text().count(before) == 1
assert original.read_text().replace(before, after, 1) == timer_source.read_text()
command = list(parent['linkCommand'])
old = next(Path(arg) for arg in command if Path(arg).name == 'main.cpp.o')
assert old.with_suffix('') == original and sha(old) == phase['mainObjectSha256']
command[command.index(str(old))] = str(timer_obj)
cache = Path(tempfile.mkdtemp(prefix='openshsm-current-vi-', dir='/private/tmp'))
exe = cache / 'OpenSHSMStockCurrentVITimer'
command[command.index('-o') + 1] = str(exe)
linked = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(linked.stdout + linked.stderr)
assert linked.returncode == 0, linked.stderr[-2500:]
retained = {}
for arg in command:
    if Path(arg).suffix in ('.o', '.a'):
        path = (Path(arg) if Path(arg).is_absolute() else root / 'export/build' / arg).resolve()
        retained[str(path)] = sha(path)
(output / 'build.json').write_text(json.dumps({
    'result': 'CURRENT_RUNTIME_EXISTING_TIMER_ONLY_MAIN_RELINKED_UNVERIFIED',
    'parentBuildSha256': sha(parent_path), 'parentComponentSha256': sha(component_path),
    'timerBuildSha256': sha(timer_path), 'phaseBuildSha256': sha(phase_path),
    'mainOriginalPath': str(original), 'mainSourcePath': str(timer_source), 'mainObjectPath': str(timer_obj),
    'patch': timer['patch'], 'linkCommand': command, 'retainedInputs': retained,
    'executablePath': str(exe), 'executableSha256': sha(exe),
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), original, timer_source]},
    'limits': ['Only existing timer-only main object reused after exact source/object/current-parent hash checks.',
        'GUI no longer publishes VI; existing native configured60Hz scheduler with its original gating/coalescing retained.',
        'Current DEC gate/IOS/exact helper/master/75guests/renderer/audio/clock/fixed sleep retained.',
        'Diagnostic PC VI-source adaptation, not physical Wii beam/region timing or verified full game behavior.',
        'Native source/link/SDK observer audit and actual current late packets/visual/audio/profile checks pending; not promoted.']}, indent=2) + '\n')
print('CURRENT_RUNTIME_EXISTING_TIMER_ONLY_MAIN_RELINKED_UNVERIFIED', exe)

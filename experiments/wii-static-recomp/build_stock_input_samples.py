"""Verify bounded PC sample composition using the existing snapshot archive and original guest helpers."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base = root / 'input-snapshot-research'
output = root / 'input-samples-research'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = base / 'build.json'
build = json.loads(build_path.read_text())
assert sha(base / 'libnwiiruntime.a') == build['archiveSha256']
assert sha(base / 'include/input/input_manager.h') == build['headerSha256']
for path, expected in build['retainedLinkInputs'].items():
    assert sha(Path(path)) == expected
button_proof = json.loads((root / 'kpad-buttons-research/native.json').read_text())
for path, expected in button_proof['retainedLinkInputs'].items():
    if Path(path).suffix == '.o':
        assert sha(Path(path)) == expected
sources = [Path('experiments/wii-static-recomp') / name for name in ['stock_input_sample_probe.cpp',
    'stock_input_sample_bridge.h', 'stock_input_connection_bridge.h']]
obj, exe = output / 'probe.cpp.o', output / 'input-sample-probe'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *build['arguments'],
    '-c', str(sources[0].resolve()), '-o', str(obj)], capture_output=True, text=True, timeout=60)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
command = list(build['linkCommand'])
probe_indices = [index for index, arg in enumerate(command) if arg.endswith('/input-snapshot-research/probe.cpp.o')]
assert len(probe_indices) == 1
command[probe_indices[0]] = str(obj)
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=60)
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=20)
(output / 'probe.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and 'PC_PRIMARY_SAMPLE_PIPELINE_PASS' in result.stdout, (result.returncode, result.stdout, result.stderr)
(output / 'build.json').write_text(json.dumps({'result': 'PC_PRIMARY_SAMPLE_PIPELINE_PASS',
    'baseBuildSha256': sha(build_path), 'recipeSha256': sha(Path(__file__)),
    'sources': {str(path): sha(path) for path in sources}, 'objectSha256': sha(obj), 'executableSha256': sha(exe),
    'logSha256': sha(output / 'probe.log'), 'linkCommand': command,
    'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file()
        and Path(arg).suffix in ('.o', '.a') and arg != str(obj)},
    'limits': ['Controlled IInputSource through actual InputManager queue; not a physical-device/game test.',
        'Callback and button helper are retained original compiled functions, with prior software750CL proofs; composed PC sample not Wii sensor equivalence.',
        'Virtual extension, radial axes, pointer scaling/deltas, neutral extension motion, per-snapshot timer step1 and newest-first batching are explicit PC policy.',
        'Primary channel only; no live SDK binding, WPAD query/status forwarding or original raw calibration/queue timing restored.']}, indent=2) + '\n')
print('PC_PRIMARY_SAMPLE_PIPELINE_PASS')

"""Check timed source boundaries, primary-only state and existing manager publication."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-test-ab'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base_path = output / 'build.json'
base = json.loads(base_path.read_text())
for path, expected in {**base['dependencies'], **base['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
source, obj = public / 'stock_test_ab_probe.cpp', output / 'probe.cpp.o'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *base['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'probe-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2000:]
command = list(base['linkCommand'])
command[command.index(str(output / 'main.cpp.o'))] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
command.insert(1, str(obj))
exe = output / 'ab-probe'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
result = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=30)
(output / 'probe.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
assert 'PRIVATE_AB_SOURCE_BOUNDARIES_QUEUE_PASS' in result.stdout
invalid = ['', '-1', '+1', ' 1', '12x', '9999999', '180001']
for value in invalid:
    refused = subprocess.run([str(exe), 'invalid'], env=dict(env, NWII_TEST_AB_AT_MS=value),
        capture_output=True, text=True, timeout=10)
    assert refused.returncode == 0 and 'PRIVATE_AB_INVALID_ENV_REFUSED' in refused.stdout
(output / 'component-verification.json').write_text(json.dumps({'result': 'PRIVATE_AB_SOURCE_BOUNDARIES_QUEUE_PASS',
    'buildSha256': sha(base_path), 'probeSourceSha256': sha(source), 'executableSha256': sha(exe),
    'logSha256': sha(output / 'probe.log'), 'verifierSha256': sha(Path(__file__).resolve()),
    'invalidTimingStringsRefused': invalid,
    'limits': ['6time boundaries/3invalid durations, primary virtual source through actual existing manager queue.',
        'Not original SDK/menu transition, physical controller, OS focus or input acceptance.']}, indent=2) + '\n')
print('PRIVATE_AB_SOURCE_BOUNDARIES_QUEUE_PASS')

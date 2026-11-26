"""Test source time bounds and actual manager publication, not original menu behavior."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-test-profile'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, expected in {**build['dependencies'], **build['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
parent_path = root / 'window-test-ab/build.json'
parent = json.loads(parent_path.read_text())
assert sha(parent_path) == build['parentBuildSha256']
command = list(parent['linkCommand'])
command[command.index(str(root / 'window-test-ab/main.cpp.o'))] = str(output / 'main.cpp.o')
command[command.index('-o') + 1] = str(output / 'OpenSHSMStockTestProfile')
assert command == build['linkCommand']
archive = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
assert sha(archive) == build['archiveSha256'] == parent['archiveSha256']
source = output / 'main.cpp'
assert sha(source) == build['sourceSha256']
assert source.read_text().replace('stock_test_profile_source.h', 'stock_test_ab_source.h').replace(
    'install_test_profile_source(', 'install_test_ab_source(') == (root / 'window-test-ab/main.cpp').read_text()
probe, obj = public / 'stock_test_profile_probe.cpp', output / 'probe.cpp.o'
compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *build['arguments'],
    '-c', str(probe), '-o', str(obj)], capture_output=True, text=True, timeout=180)
assert compiled.returncode == 0, compiled.stderr[-3000:]
command[command.index(str(output / 'main.cpp.o'))] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
command.insert(1, str(obj))
exe = output / 'profile-probe'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
result = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=30)
(output / 'probe.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and 'PRIVATE_PROFILE_BOUNDARIES_QUEUE_PASS' in result.stdout, result.stderr
(output / 'component-verification.json').write_text(json.dumps({
    'result': 'PRIVATE_PROFILE_BOUNDARIES_QUEUE_PASS', 'buildSha256': sha(build_path),
    'probeSourceSha256': sha(probe), 'executableSha256': sha(exe), 'logSha256': sha(output / 'probe.log'),
    'verifierSha256': sha(Path(__file__).resolve()),
    'limits': ['10time boundaries/3bad schedule bounds/7invalid strings, channel1 preserved.',
        'Actual manager publication tested; no physical controller, original SDK/menu or save acceptance.']}, indent=2) + '\n')
print('PRIVATE_PROFILE_BOUNDARIES_QUEUE_PASS')

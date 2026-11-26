"""Compile guards against the actual specialized STM device and existing kernel."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'mass-stm-async-boot'
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
sources = [experiment / 'stm_async_device_probe.cpp', output / 'stm_device.cpp', root / 'stm-open-native/ios_kernel.cpp']
for path in sources[1:]:
    assert build['sourceHashes'][str(path)] == sha(path)
exe = output / 'stm-async-device-probe'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-I', str(runtime / 'include'),
    *map(str, sources), '-o', str(exe)], capture_output=True, text=True, timeout=60)
(output / 'device-probe-build.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
assert result.returncode == 0 and not result.stderr
assert result.stdout.splitlines()[-1] == 'STM_ASYNC_DEVICE deferred1 malformed8 duplicate1 retained'
(output / 'device-guards.json').write_text(json.dumps({'result': 'ACTUAL_STM_PENDING_OWNER_DEFERRED_MALFORMED8_DUPLICATE1_RETAINED_PASS',
    'verifierSha256': sha(Path(__file__)), 'buildSha256': sha(output / 'build.json'),
    'sourceHashes': {str(path): sha(path) for path in sources}, 'executableSha256': sha(exe),
    'limits': ['Device/kernel ownership and malformed-request guards only; not game IRQ/timing/callback-completion proof.']}, indent=2) + '\n')
print(result.stdout)

"""Compare existing actual kernel/FS open results with original pending coexistence oracle."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'fs-pending-device'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_fs_pending_dolphin.py')], check=True)
oracle_path = root / 'dolphin-fs-pending/comparison.json'
oracle = json.loads(oracle_path.read_text())
sources = [experiment / 'fs_pending_device_probe.cpp', root / 'mass-stm-async-boot/stm_device.cpp',
    root / 'stm-open-native/ios_kernel.cpp', runtime / 'src/hle/devices/fs_device.cpp', runtime / 'src/hw/mmio_dispatcher.cpp']
async_build = json.loads((root / 'mass-stm-async-boot/build.json').read_text())
for path in sources[1:3]:
    assert sha(path) == async_build['sourceHashes'][str(path)]
exe = output / 'fs-pending-device-probe'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-I', str(runtime / 'include'),
    *map(str, sources), '-o', str(exe)], capture_output=True, text=True, timeout=60)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
(output / 'execution.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and not result.stderr
rows = [list(map(int, line.split()[1:])) for line in result.stdout.splitlines() if line.startswith('FS_PENDING_DEVICE ')]
assert rows == [[row['index'], row['returnValue']] for row in oracle['observations']]
(output / 'comparison.json').write_text(json.dumps({'result': 'EXISTING_KERNEL_FS13_OPEN_RESULTS_MATCH_ORIGINAL_PENDING_OWNER_PRESERVED',
    'verifierSha256': sha(Path(__file__)), 'oracleSha256': sha(oracle_path), 'sourceHashes': {str(path): sha(path) for path in sources},
    'executableSha256': sha(exe), 'logSha256': sha(output / 'execution.log'), 'rows': rows,
    'limits': ['Isolated component with unchanged vendor FS class; open initializes synthetic in-memory VNand entries, unused and unverified.',
        'No FS file/IOCTL/read/write/close operations or filesystem writes; not connected to native startup.',
        'Descriptor results and STM device ownership only, not PPC reply/free/cache/IRQ equivalence.']}, indent=2) + '\n')
print('PASS existing kernel/FS: 13 original OPEN results, STM pending tuple/owner retained; isolated component only')

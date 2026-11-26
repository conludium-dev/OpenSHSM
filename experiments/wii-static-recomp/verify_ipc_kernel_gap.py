"""Check actual pinned IOSKernel missing-device result against the original reply."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'ipc-kernel-gap'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_ipc_pending_dolphin.py')], check=True)
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sources = [experiment / 'ipc_kernel_probe.cpp', upstream / 'src/hle/ios_kernel.cpp']
exe = output / 'ipc-kernel-probe'
build = subprocess.run(['clang++', '-std=c++20', '-O2', '-include', 'bit', '-I', str(upstream / 'include'),
                        *map(str, sources), '-o', str(exe)], capture_output=True, text=True, timeout=60)
assert build.returncode == 0, build.stderr
native = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
assert native.returncode == 0, native
(output / 'native.log').write_text(native.stdout + native.stderr)
rows = [list(map(int, line.split()[1:])) for line in native.stdout.splitlines() if line.startswith('IPC_KERNEL_CASE ')]
oracle_path = private / 'dolphin-ipc-pending/comparison.json'
oracle = json.loads(oracle_path.read_text())
assert len(rows) == len(oracle['observations']) == 8
for (index, result), row in zip(rows, oracle['observations']):
    assert index == row['index'] and result == -106 and row['replyResult'] == -6
report = {'result': 'PINNED_IOS_KERNEL_MISSING_DEVICE_ERROR_FS106_DIFFERS_ORIGINAL_IPC6', 'cases': 8,
          'nativeResult': -106, 'originalResult': -6, 'oracleSha256': sha(oracle_path),
          'sourceSha256': {str(path): sha(path) for path in sources},
          'headerSha256': {name: sha(upstream / name) for name in ('include/runtime/ios_device.h', 'include/runtime/ios_kernel.h', 'include/runtime/cpu_context.h')},
          'executableSha256': sha(exe), 'nativeLogSha256': sha(output / 'native.log'), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Actual vendor IOSKernel::open component with empty device registry and known nonexistent device path.',
                     'No full device registration, PPC packet parsing, request/reply transport or ordinary boot activation.',
                     'Do not globally replace FS error106: original IPC missing-device error6 is a distinct context.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('CONFIRMED existingIOSKernel unknown-device result-106 differsoriginal-6; realproducerintegration pending')

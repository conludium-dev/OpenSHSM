"""Verify a context-specific private copy patch without changing vendor FS error constants."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'ipc-kernel-fixed'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_ipc_kernel_gap.py')], check=True)
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
vendor = upstream / 'src/hle/ios_kernel.cpp'
body = vendor.read_text()
needle = '    return IPC_ENOENT;'
assert body.count(needle) == 1
patched = output / 'ios_kernel.cpp'
patched.write_text(body.replace(needle, '    return -6;'))
probe = experiment / 'ipc_kernel_fixed_probe.cpp'
exe = output / 'ipc-kernel-fixed-probe'
build = subprocess.run(['clang++', '-std=c++20', '-O2', '-include', 'bit', '-I', str(upstream / 'include'),
                        str(probe), str(patched), '-o', str(exe)], capture_output=True, text=True, timeout=60)
assert build.returncode == 0, build.stderr
native = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
assert native.returncode == 0, native
(output / 'native.log').write_text(native.stdout + native.stderr)
oracle_path = private / 'dolphin-ipc-pending/comparison.json'
oracle = json.loads(oracle_path.read_text())
rows = [line.split() for line in native.stdout.splitlines() if line.startswith('IPC_KERNEL_FIXED ')]
assert len(rows) == len(oracle['observations']) == 8
for row, original in zip(rows, oracle['observations']):
    assert int(row[1]) == original['index'] and int(row[2]) == original['replyResult'] == -6
assert 'IPC_DEVICE_ERROR_FORWARDED -106\n' in native.stdout
assert vendor.read_text() == body and 'constexpr int32_t IPC_ENOENT = -106;' in (upstream / 'include/runtime/ios_device.h').read_text()
report = {'result': 'PRIVATE_IOS_KERNEL_UNKNOWN_DEVICE_BRANCH8_MATCH_DEVICE_ERROR_FORWARDING_PRESERVED', 'cases': 8,
          'forwardedErrorContracts': 1, 'oracleSha256': sha(oracle_path), 'vendorSourceSha256': sha(vendor),
          'patchedSourceSha256': sha(patched), 'probeSha256': sha(probe), 'headerSha256': sha(upstream / 'include/runtime/ios_device.h'),
          'executableSha256': sha(exe), 'nativeLogSha256': sha(output / 'native.log'), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Private mechanical one-return patch in missing-device branch, vendor source/header unchanged.',
                     'Actual IOSKernel component tested; provided error fixture tests forwarding only, not filesystem behavior.',
                     'No PPC packet parser/reply metadata/transport/full device registration or ordinary boot activation.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS privateIOSKernel unknown-device result8matches/-6; device error-106 forwarded, vendor unchanged')

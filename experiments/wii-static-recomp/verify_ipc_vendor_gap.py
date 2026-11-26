"""Execute the pinned vendor IPC backend against original control-reset observations."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'ipc-vendor-gap'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_ipc_reset_dolphin.py')], check=True)
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sources = [experiment / 'ipc_vendor_probe.cpp', *[upstream / name for name in ('src/hw/hw_ipc.cpp', 'src/hw/hw_pi.cpp', 'src/hw/mmio_dispatcher.cpp')]]
exe = output / 'ipc-vendor-probe'
build = subprocess.run(['clang++', '-std=c++20', '-O2', '-include', 'bit', '-I', str(upstream / 'include'),
                        *map(str, sources), '-o', str(exe)], capture_output=True, text=True, timeout=60)
(output / 'build.log').write_text(build.stdout + build.stderr)
assert build.returncode == 0, build.stderr
native = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
(output / 'native.log').write_text(native.stdout + native.stderr)
assert native.returncode == 0, native
rows = [list(map(int, line.split()[1:])) for line in native.stdout.splitlines() if line.startswith('IPC_VENDOR_CASE ')]
oracle_path = private / 'dolphin-ipc-reset/comparison.json'
oracle = json.loads(oracle_path.read_text())
assert len(rows) == len(oracle['observations']) == 32
mismatches = []
for native_row, original in zip(rows, oracle['observations']):
    index, control_before, control_after, arm_before, arm_after = native_row
    assert index == original['index'] and control_before == original['controlBefore']
    assert arm_before == arm_after == original['armMessageBefore'] == original['armMessageAfter'] == 0
    assert control_after == control_before
    if control_after != original['controlAfter']:
        mismatches.append({'index': index, 'mask': hex(original['requestedMask']),
                           'originalControlAfter': original['controlAfter'], 'vendorControlAfter': control_after})
assert len(mismatches) == 12
assert all(int(row['mask'], 16) & 0x40000000 and row['originalControlAfter'] == 0 and row['vendorControlAfter'] in (16, 32, 48) for row in mismatches)
report = {'result': 'CURRENT_VENDOR_IPC_BACKEND_FAILS_ORIGINAL_RESET_CONTROL_12_OF_32_CASES',
          'cases': 32, 'mismatches': mismatches, 'matchingCases': 20, 'oracleSha256': sha(oracle_path),
          'sourceSha256': {str(path): sha(path) for path in sources},
          'headerSha256': {name: sha(upstream / name) for name in ('include/runtime/hw/hw.h', 'include/runtime/hw/mmio_dispatcher.h', 'include/runtime/cpu_context.h', 'include/runtime/config.h')},
          'executableSha256': sha(exe), 'nativeLogSha256': sha(output / 'native.log'), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Negative backend compatibility test; matching zero/control-preserving cases do not establish IPC support.',
                     'Synthetic control/zero ARM-message fixtures; duplicate NI labels from oracle are not native PPC/FP execution.',
                     'No full IOS/request/event/reset proof, physical Wii comparison or native boot activation.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('CONFIRMED vendorIPCreset mismatch12/32; nativebootIPCmask remains blocked')

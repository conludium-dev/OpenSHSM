"""Verify control projection on existing vendor storage against retained original observations."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'ipc-control-backend'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_ipc_control_dolphin.py')], check=True)
oracle_path = private / 'dolphin-ipc-control/comparison.json'
oracle = json.loads(oracle_path.read_text())
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sources = [experiment / 'ipc_control_probe.cpp', upstream / 'src/hw/hw_pi.cpp', upstream / 'src/hw/mmio_dispatcher.cpp']
exe = output / 'ipc-control-probe'
build = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O2', '-include', 'bit', '-I', str(experiment),
                        '-I', str(upstream / 'include'), '-I', str(upstream / 'src/hw'), *map(str, sources), '-o', str(exe)],
                       capture_output=True, text=True, timeout=60)
(output / 'build.log').write_text(build.stdout + build.stderr)
assert build.returncode == 0, build.stderr
inputs = ''.join(f"{row['index']} {row['controlBefore']} {row['value']} {row['armMessage']}\n" for row in oracle['observations'])
native = subprocess.run([str(exe.resolve())], input=inputs, capture_output=True, text=True, timeout=30)
(output / 'native.log').write_text(native.stdout + native.stderr)
assert native.returncode == 0, native.stderr
rows = [list(map(int, line.split()[1:])) for line in native.stdout.splitlines() if line.startswith('IPC_CONTROL ')]
assert len(rows) == 8 and 'IPC_CONTROL_GUARDS 8\n' in native.stdout
differences = []
for row, original in zip(rows, oracle['observations']):
    index, vendor_first, vendor_x2, actual_first, actual_x2, message_first, message_x2 = row
    assert index == original['index'] and actual_first == original['controlAfter'] and actual_x2 == original['controlAfterX2']
    assert message_first == message_x2 == original['armMessage']
    assert vendor_first == original['controlAfter'] and vendor_x2 == 0x30 != original['controlAfterX2']
    differences.append({'index': index, 'vendorAfterX2': vendor_x2, 'originalAfterX2': original['controlAfterX2']})
report = {'result': 'CONTROL_W1C_X2_PROJECTION8_ORIGINAL_MATCH_VENDOR_NEGATIVE8_PASS', 'cases': 8,
          'refusalCases': 8, 'vendorMismatches': differences, 'oracleSha256': sha(oracle_path),
          'sourceHashes': {str(path): sha(path) for path in sources},
          'backendSha256': sha(experiment / 'ipc_reset_backend.cpp'), 'headerSha256': sha(experiment / 'ipc_reset_backend.h'),
          'vendorSha256': sha(upstream / 'src/hw/hw_ipc.cpp'), 'verifierSha256': sha(Path(__file__)),
          'executableSha256': sha(exe), 'nativeLogSha256': sha(output / 'native.log'),
          'limits': ['Existing vendor IPC storage, strict non-request control projection only; no second registry or vendor edits.',
                     'Seeded ACK/reply fixture states and measured read-only control/message output, not native request production.',
                     'Original IRQ cause changes are retained in oracle but not implemented/accepted here.',
                     'Send bit/active CPU/MMU/delay refused with state preservation; no full IRQ/IOS/cache/boot activation.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS8 original control/X2 states, vendor-negative8, refusal8; live backend not activated')

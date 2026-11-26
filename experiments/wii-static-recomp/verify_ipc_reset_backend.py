"""Check bounded quiescent reset on existing vendor registers; no live activation."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'ipc-reset-backend'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_ipc_reset_dolphin.py')], check=True)
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sources = [experiment / 'ipc_reset_probe.cpp', experiment / 'ipc_reset_backend.cpp',
           upstream / 'src/hw/hw_pi.cpp', upstream / 'src/hw/mmio_dispatcher.cpp']
exe = output / 'ipc-reset-probe'
build = subprocess.run(['clang++', '-std=c++20', '-O2', '-include', 'bit', '-I', str(experiment),
                        '-I', str(private / 'mass-pi-mask'), '-I', str(upstream / 'include'), '-I', str(upstream / 'src/hw'), *map(str, sources), '-o', str(exe)],
                       capture_output=True, text=True, timeout=60)
(output / 'build.log').write_text(build.stdout + build.stderr)
assert build.returncode == 0, build.stderr
native = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
(output / 'native.log').write_text(native.stdout + native.stderr)
assert native.returncode == 0, native
rows = [list(map(int, line.split()[1:])) for line in native.stdout.splitlines() if line.startswith('IPC_RESET_CASE ')]
oracle_path = private / 'dolphin-ipc-reset/comparison.json'
oracle = json.loads(oracle_path.read_text())
assert len(rows) == len(oracle['observations']) == 32
for native_row, original in zip(rows, oracle['observations']):
    index, before, after, arm_before, arm_after, mask = native_row
    assert index == original['index'] and before == original['controlBefore'] and after == original['controlAfter']
    assert arm_before == arm_after == original['armMessageBefore'] == original['armMessageAfter'] == 0
    assert mask == (0x40000000 if original['requestedMask'] & 0x40000000 else original['requestedMask'])
assert 'IPC_RESET_INFLIGHT_GUARD 1\n' in native.stdout
assert 'IPC_RESET_FRONTEND cases=8 guards=8\n' in native.stdout
report = {'result': 'QUIESCENT_VENDOR_REGISTER_RESET32_MATCH_LIVE_NOT_ACTIVATED', 'cases': 32, 'inflightRefusalCases': 1,
          'frontendCases': 8, 'frontendRefusalCases': 8, 'frontendSha256': sha(experiment / 'ipc_reset_adapter.h'),
          'seedHeaderSha256': sha(private / 'mass-pi-mask/loader-bat-seed.h'),
          'oracleSha256': sha(oracle_path), 'sourceSha256': {str(path): sha(path) for path in sources},
          'vendorIpcSha256': sha(upstream / 'src/hw/hw_ipc.cpp'), 'backendHeaderSha256': sha(experiment / 'ipc_reset_backend.h'),
          'executableSha256': sha(exe), 'nativeLogSha256': sha(output / 'native.log'), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Same vendor IPC message/control storage; missing mask storage added once, not a second runtime.',
                     'Quiescent control/message projection only; in-flight reset deliberately refused.',
                     'Synchronous quiescent adaptation does not implement IOS queues/scheduled updates/GPIO/device reset.',
                     'Frontend contracts tested; original store lowering/full native module integration/live activation not verified.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS boundedquiescentreset32controls/8frontendcases/8rollbackguards/1inflightguard; no liveIPCactivation')

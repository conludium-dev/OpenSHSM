"""Check observed causal ordering with the existing vendor scheduler/register storage."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'ipc-event-order'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_ipc_pending_dolphin.py')], check=True)
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sources = [experiment / 'ipc_event_order_probe.cpp', upstream / 'src/core/event_scheduler.cpp',
           upstream / 'src/hw/hw_pi.cpp', upstream / 'src/hw/mmio_dispatcher.cpp']
exe = output / 'ipc-event-order-probe'
build = subprocess.run(['clang++', '-std=c++20', '-O2', '-include', 'bit', '-I', str(experiment),
                        '-I', str(upstream / 'include'), '-I', str(upstream / 'src/hw'), *map(str, sources), '-o', str(exe)],
                       capture_output=True, text=True, timeout=60)
(output / 'build.log').write_text(build.stdout + build.stderr)
assert build.returncode == 0, build.stderr
native = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
(output / 'native.log').write_text(native.stdout + native.stderr)
assert native.returncode == 0, native
rows = [list(map(int, line.split()[1:])) for line in native.stdout.splitlines() if line.startswith('IPC_EVENT_CASE ')]
oracle_path = private / 'dolphin-ipc-pending/comparison.json'
oracle = json.loads(oracle_path.read_text())
assert len(rows) == len(oracle['observations']) == 8
for row, original in zip(rows, oracle['observations']):
    index, immediate_control, immediate_message, later_control, later_message = row
    assert index == original['index']
    assert (immediate_control, immediate_message, later_control, later_message) == (
        original['controlImmediate'], original['messageImmediate'], original['controlLater'], original['messageLater'])
mutant_source = output / 'drop-event-mutant.cpp'
body = (experiment / 'ipc_event_order_probe.cpp').read_text()
needle = '    if (value & 0x40000000) {\n'
assert body.count(needle) == 1
mutant_source.write_text(body.replace(needle, needle + '        EventScheduler::get().reset();\n'))
mutant_exe = output / 'drop-event-mutant'
mutant_build = subprocess.run(['clang++', '-std=c++20', '-O2', '-include', 'bit', '-I', str(experiment),
                              '-I', str(upstream / 'include'), '-I', str(upstream / 'src/hw'), str(mutant_source),
                              *map(str, sources[1:]), '-o', str(mutant_exe)], capture_output=True, text=True, timeout=60)
assert mutant_build.returncode == 0, mutant_build.stderr
mutant = subprocess.run([str(mutant_exe)], capture_output=True, text=True, timeout=30)
assert mutant.returncode == 9, (mutant.returncode, mutant.stdout, mutant.stderr)
(output / 'mutant.log').write_text(mutant.stdout + mutant.stderr)
report = {'result': 'ISOLATED_VENDOR_EVENT_ORDER8_MATCH_CONTROL_MESSAGE_PROJECTION', 'cases': 8,
          'eventDropMutantDetected': True, 'mutantSourceSha256': sha(mutant_source),
          'oracleSha256': sha(oracle_path), 'sourceSha256': {str(path): sha(path) for path in sources},
          'backendSha256': sha(experiment / 'ipc_reset_backend.cpp'), 'vendorIpcSha256': sha(upstream / 'src/hw/hw_ipc.cpp'),
          'schedulerHeaderSha256': sha(upstream / 'include/runtime/event_scheduler.h'),
          'executableSha256': sha(exe), 'nativeLogSha256': sha(output / 'native.log'), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Existing vendor EventScheduler and IPC register storage; no second scheduler/reset of event heap on hardware mask write.',
                     'Synthetic producer supplies observed reply pointer; no IOS request execution or original PPC integration.',
                     'Adapter ticks1/2 encode causal ordering, not measured physical/TB timing; NI labels duplicate the same transport inputs.',
                     'Only isolated probe; full queue/reset/GPIO/device effects and ordinary boot activation remain unverified.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS8observedcausalstates on existingEventScheduler/IPCstorage; no IOS/bootactivation')

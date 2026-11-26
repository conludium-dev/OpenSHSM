"""Compare bounded physical packet/kernel/reply/event coupling with retained original observations."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'ipc-producer'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_ipc_kernel_fixed.py')], check=True)
subprocess.run(['python3', str(experiment / 'verify_ipc_packet_dolphin.py')], check=True)
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
kernel = private / 'ipc-kernel-fixed/ios_kernel.cpp'
vendor_kernel = upstream / 'src/hle/ios_kernel.cpp'
assert kernel.read_text() == vendor_kernel.read_text().replace('    return IPC_ENOENT;', '    return -6;')
sources = [experiment / 'ipc_producer_probe.cpp', kernel, upstream / 'src/core/event_scheduler.cpp',
           upstream / 'src/hw/hw_pi.cpp', upstream / 'src/hw/mmio_dispatcher.cpp']
exe = output / 'ipc-producer-probe'
build = subprocess.run(['clang++', '-std=c++20', '-O2', '-include', 'bit', '-I', str(experiment),
                        '-I', str(upstream / 'include'), '-I', str(upstream / 'src/hw'), *map(str, sources), '-o', str(exe)],
                       capture_output=True, text=True, timeout=60)
(output / 'build.log').write_text(build.stdout + build.stderr)
assert build.returncode == 0, build.stderr
native = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
(output / 'native.log').write_text(native.stdout + native.stderr)
assert native.returncode == 0, native
rows = [list(map(int, line.split()[1:])) for line in native.stdout.splitlines() if line.startswith('IPC_PRODUCER_CASE ')]
oracle_path = private / 'dolphin-ipc-packet/comparison.json'
oracle = json.loads(oracle_path.read_text())
assert len(rows) == len(oracle['observations']) == 8
for row, original in zip(rows, oracle['observations']):
    index, immediate_control, immediate_message, later_control, later_message, command, result, fd, fpscr = row
    assert index == original['index']
    assert (immediate_control, immediate_message, later_control, later_message) == (
        original['controlImmediate'], original['messageImmediate'], original['controlLater'], original['messageLater'])
    assert command == original['replyCommand'] == 8 and result == original['replyResult'] == -6 and fd == 1
    assert fpscr == original['ni'] * 4
packets = [line.split()[1:] for line in native.stdout.splitlines() if line.startswith('IPC_PRODUCER_PACKET ')]
assert len(packets) == 8
for (index, packet), original in zip(packets, oracle['observations']):
    assert int(index) == original['index'] and packet == original['replyPacketHex']
assert 'IPC_PRODUCER_GUARDS 12\n' in native.stdout
report = {'result': 'BOUNDED_PACKET_KERNEL_REPLY_EVENT_COUPLING8_MATCH_NO_BOOT_ACTIVATION', 'cases': 8, 'malformedRollbackCases': 12, 'replyBytesCompared': 512,
          'oracleSha256': sha(oracle_path), 'sourceSha256': {str(path): sha(path) for path in sources},
          'helperSha256': {name: sha(experiment / name) for name in ('ipc_open_packet.h', 'ipc_event_order_probe.cpp', 'ipc_reset_backend.cpp', 'ipc_reset_backend.h')},
          'vendorSourceSha256': {name: sha(upstream / name) for name in ('src/hw/hw_ipc.cpp', 'include/runtime/ios_kernel.h', 'include/runtime/ios_device.h', 'include/runtime/event_scheduler.h')},
          'executableSha256': sha(exe), 'nativeLogSha256': sha(output / 'native.log'), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Native adapter parses bounded physical-MEM1 read-only OPEN packet and calls actual existing IOSKernel; not full IOS command/device support.',
                     'All64reply bytes and observed control/message states match8original fixtures.',
                     'Existing vendor EventScheduler/register storage reused; synthetic ACK stage and adapter ticks1/2, not Wii timing.',
                     'No original PPC request sender or full boot/IOS/GPIO/reset activation; missing regions/modes/deferred replies remain unsupported.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS8packet→actualIOSKernel→replyheader→existingscheduler cases/12malformedrollback; no bootactivation')

"""Couple measured OPEN to the existing event-order mechanism, not general boot permission."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
profile = root / 'stm-open-native'
output = root / 'stm-transport-native'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_stm_open_native.py')], check=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
for name, parent in (('ipc_open_packet.h', profile), ('ipc_event_order_probe.cpp', experiment), ('stm_transport_host.cpp', experiment)):
    (output / name).write_bytes((parent / name).read_bytes())
sources = [output / 'stm_transport_host.cpp', profile / 'ios_kernel.cpp', runtime / 'src/hle/devices/stm_device.cpp',
    runtime / 'src/core/event_scheduler.cpp', runtime / 'src/hw/hw_pi.cpp', runtime / 'src/hw/mmio_dispatcher.cpp']
exe = output / 'stm-transport-probe'
command = ['arch', '-arm64', 'clang++', '-std=c++20', '-O2', '-include', 'bit',
    '-I', str(output), '-I', str(experiment), '-I', str(runtime / 'include'), '-I', str(runtime / 'src/hw'),
    *map(str, sources)]
result = subprocess.run(command + ['-o', str(exe)], capture_output=True, text=True, timeout=60)
(output / 'build.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
proofs = {}
for mode, directory in (('startup', 'dolphin-stm-open-startup'), ('ix1', 'dolphin-stm-open')):
    result = subprocess.run([str(exe), mode], capture_output=True, text=True, timeout=20)
    (output / (mode + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and not result.stderr, result.stdout + result.stderr
    lines = result.stdout.splitlines()
    states = [list(map(int, line.split()[1:])) for line in lines if line.startswith('STM_TRANSPORT ')]
    packets = [line.split()[1:] for line in lines if line.startswith('STM_TRANSPORT_PACKET ')]
    oracle_path = root / directory / 'comparison.json'
    oracle = json.loads(oracle_path.read_text())
    assert len(states) == len(packets) == len(oracle['observations']) == 16
    for row, packet, original in zip(states, packets, oracle['observations']):
        index, fields = original['index'], original['states']
        assert row == [index, fields[3], fields[4], fields[6], fields[7], fields[9], original['replyResult'], 1]
        assert packet == [str(index), original['replyPacketHex']]
    proofs[mode] = sha(oracle_path)
mutants = {}
for name, macro in (('missing-production', 'SHSM_DROP_STM_PRODUCER'), ('wrong-result', 'SHSM_WRONG_STM_RESULT')):
    mutant = output / name
    build = subprocess.run(command + ['-D' + macro, '-o', str(mutant)], capture_output=True, text=True, timeout=60)
    assert build.returncode == 0, build.stderr
    result = subprocess.run([str(mutant), 'startup'], capture_output=True, text=True, timeout=20)
    (output / (name + '.log')).write_text(result.stdout + result.stderr)
    if name == 'missing-production':
        assert result.returncode == 4 and not result.stderr
    else:
        assert result.returncode == 0 and not result.stderr
        first = next(line for line in result.stdout.splitlines() if line.startswith('STM_TRANSPORT 0 '))
        assert int(first.split()[-2]) == 0x42
        assert int(first.split()[-2]) != json.loads((root / 'dolphin-stm-open-startup/comparison.json').read_text())['observations'][0]['replyResult']
    mutants[name] = {'executableSha256': sha(mutant), 'logSha256': sha(output / (name + '.log'))}
(output / 'comparison.json').write_text(json.dumps({'result': 'EXISTING_SHARED_IPC_EVENT_REPLY_STM32_ORIGINAL_CAUSAL_ENDPOINTS_MATCH',
    'verifierSha256': sha(Path(__file__)), 'profileProofSha256': sha(profile / 'comparison.json'), 'originalProofs': proofs,
    'sourceHashes': {str(path): sha(path) for path in sources}, 'eventMechanismSha256': sha(experiment / 'ipc_event_order_probe.cpp'),
    'headerSha256': sha(output / 'ipc_open_packet.h'), 'executableSha256': sha(exe),
    'mutantsRejected': mutants,
    'limits': ['Same event heap/register storage/kernel/parser; lab stimulus seeds send and schedules ACK.',
        'Ticks1/2/8/9 are explicit PC causal fixtures, not original timing; PI chronology not compared.',
        'Real kernel result generated once inside existing delayed reply event, not supplied FD/success.',
        'No original PPC caller/CPU interrupt/wakeup chain or current boot admission.']}, indent=2) + '\n')
print('PASS32 scheduled STM/missing causal ACK/reply/payload endpoints; hold-beforeACK/single production;2mutants')

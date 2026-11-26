"""Compare complete original UART writes, stalled completion and full FIFO."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'uart-native'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
assert build['builderSha256'] == sha(experiment / 'build_uart_native.py')
assert build['hostSourceSha256'] == sha(experiment / 'uart_host.cpp')
assert build['backendSha256'] == sha(experiment / 'exi_getid_backend.h')
assert build['baseExecutionSha256'] == sha(private / 'exi-getid-native/execution.json')
for path, digest in build['sourceHashes'].items():
    assert sha(Path(path)) == digest
subprocess.run(['python3', str(experiment / 'verify_uart_dolphin.py')], check=True)
subprocess.run(['python3', str(experiment / 'verify_exi_getid_native.py')], check=True)
oracle_path = private / 'dolphin-uart/comparison.json'
assert build['oracleSha256'] == sha(oracle_path)
oracle = json.loads(oracle_path.read_text())
exe = output / 'uart-probe'
assert build['executableSha256'] == sha(exe)
def run(mode):
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', mode], capture_output=True, text=True, timeout=30)
    (output / (mode + '.log')).write_text(result.stdout + result.stderr)
    rows = [list(map(int, line.split()[1:])) for line in result.stdout.splitlines() if line.startswith('UART_CASE ')]
    phases = [list(map(int, line.split()[1:])) for line in result.stdout.splitlines() if line.startswith('UART_PHASE ')]
    transmitted = [list(map(int, line.split()[1:])) for line in result.stdout.splitlines() if line.startswith('UART_BYTES ')]
    return result, rows, phases, transmitted
expected = [[row['index'], row['returnValue'], row['payloadWordAfter'], row['csrBeforeFixtureClear'], row['controlBefore'], row['dataBefore'],
    row['causeBeforeFixtureClear'], row['causeAfter'], row['csrAfter'], row['controlAfter'], row['dataAfter'], row['uartInitializedAfter'],
    *row['ecbAfter'], *bytes.fromhex(row['bufferAfterHex'])] for row in oracle['observations']]
expected_phases = [[row['index'], *phase] for row in oracle['observations'] for phase in row['phases']]
expected_bytes = [[row['index'], *bytes.fromhex(row['payloadHex']).replace(b'\n', b'\r')] for row in oracle['observations']]
normal, rows, phases, transmitted = run('normal')
assert normal.returncode == 0 and rows == expected and phases == expected_phases and transmitted == expected_bytes
lost, lost_rows, _, _ = run('lost')
assert lost.returncode == 20 and not lost_rows and 'GetID instruction budget exceeded' in lost.stderr
full, full_rows, _, full_bytes = run('full')
assert full.returncode == 21 and not full_rows and not full_bytes and 'GetID instruction budget exceeded' in full.stderr
guards, _, _, _ = run('guards')
assert guards.returncode == 0 and 'UART_GUARDS 7' in guards.stdout
report = {'result': 'WHOLE_UART16_96_PHASES_AND_BYTES_MATCH_ORIGINAL', 'cases': 16, 'phaseSnapshots': len(phases),
    'lostCompletionDetected': True, 'fullQueueDoesNotTransmit': True, 'statePreservingRefusals': 7,
    'buildSha256': sha(build_path), 'oracleSha256': sha(oracle_path), 'verifierSha256': sha(Path(__file__)),
    'limits': ['Prepared whole UART0/1/clock4 init/write with NI0/1, lengths1..4/EXTINT fixture; not physical Wii/full CPU state/cache timing.',
        'Compare CSR/control/data/PI/ECB/init flag/normalized buffer and96phase snapshots; byte sink is a PC adaptation.',
        'Empty FIFO response0 and synchronous completion measured in Dolphin; ROM/font/SRAM/unrecognized device requests stay refused.',
        'GetID0/2 regression retains16cases/32phases/two mutations/8refusals; full startup/menu remains pending.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS16 whole UART/96phases/byte stream; lost completion/full queue/refusals7; GetID regression retained')

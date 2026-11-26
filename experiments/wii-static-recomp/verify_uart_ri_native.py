"""Compare RI UART whole calls/phases/bytes and retained negative completion paths."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'uart-ri-native'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_uart_ri_dolphin.py')], check=True)
build = json.loads((output / 'build.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_uart_ri_native.py')
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
base = json.loads((private / 'mass-memory-protection-boot/boot.json').read_text())
assert all(row['sourceSha256'] == old['sourceSha256'] for row, old in zip(build['records'], base['records']))
oracle = json.loads((private / 'dolphin-uart/comparison.json').read_text())
expected = [[row['index'], row['returnValue'], row['payloadWordAfter'], row['csrBeforeFixtureClear'], row['controlBefore'], row['dataBefore'],
    row['causeBeforeFixtureClear'], row['causeAfter'], row['csrAfter'], row['controlAfter'], row['dataAfter'], row['uartInitializedAfter'],
    *row['ecbAfter'], *bytes.fromhex(row['bufferAfterHex'])] for row in oracle['observations']]
expected_phases = [[row['index'], *phase] for row in oracle['observations'] for phase in row['phases']]
expected_bytes = [[row['index'], *bytes.fromhex(row['payloadHex']).replace(b'\n', b'\r')] for row in oracle['observations']]
exe = output / 'uart-ri-probe'
assert build['executableSha256'] == sha(exe)
for mode, code in [('normal', 0), ('lost', 20), ('full', 21), ('guards', 0)]:
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', mode], capture_output=True, text=True, timeout=30)
    assert result.returncode == code == build['results'][mode]['returnCode']
    assert build['results'][mode]['logSha256'] == sha(output / (mode + '.log'))
    assert result.stdout + result.stderr == (output / (mode + '.log')).read_text()
    rows = [list(map(int, line.split()[1:])) for line in result.stdout.splitlines() if line.startswith('UART_CASE ')]
    phases = [list(map(int, line.split()[1:])) for line in result.stdout.splitlines() if line.startswith('UART_PHASE ')]
    stream = [list(map(int, line.split()[1:])) for line in result.stdout.splitlines() if line.startswith('UART_BYTES ')]
    if mode == 'normal':
        assert rows == expected and phases == expected_phases and stream == expected_bytes
    elif mode in ('lost', 'full'):
        assert not rows and 'GetID instruction budget exceeded' in result.stderr
        if mode == 'full':
            assert not stream
    else:
        assert result.stdout == 'RI_UART_GUARDS 8\nUART_GUARDS 7\n' and not result.stderr
(output / 'comparison.json').write_text(json.dumps({'result': 'RI_UART16_96_PHASES_BYTES_AND_NEGATIVE_COMPLETION_PASS',
    'buildSha256': sha(output / 'build.json'), 'verifierSha256': sha(Path(__file__)),
    'riOracleSha256': sha(private / 'dolphin-uart-ri/comparison.json'),
    'limits': ['RI opt-in only measured UART0/1/clock4 and its original SDK interrupt-mask/DI-config helper sites.',
        'Both source batches unchanged; existing transport reused, no new device or returned data.',
        'Seven legacy invalid requests now also refuse due RI caller restrictions; not seven independent backend negatives.',
        'Physical Wii/interrupt delivery/full boot/first menu remain unverified.']}, indent=2) + '\n')
print('PASS RI UART16/96phases/byte stream; missing completion/full FIFO refuse; original sources unchanged')

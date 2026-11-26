"""Validate original EE-enabled UART endpoints against retained original RI control."""
from pathlib import Path
import base64
import hashlib
import json
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'dolphin-uart-ee'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_uart_ri_dolphin.py')], check=True)
generation = json.loads((output / 'generation.json').read_text())
capture = json.loads((output / 'fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
control_generation = json.loads((private / 'dolphin-uart-ri/generation.json').read_text())
control = json.loads((private / 'dolphin-uart-ri/fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
assert generation['generatorSha256'] == sha(experiment / 'build_uart_ee_dolphin.py')
assert generation['eeParentSha256'] == sha(experiment / 'build_uart_unobserved_dolphin.py')
assert generation['baseUartGeneratorSha256'] == sha(experiment / 'build_uart_dolphin.py')
assert generation['wrapperSha256'] == sha(experiment / 'run_uart_ee_dolphin.ps1') == capture['scriptSha256'].lower()
assert generation['harnessSha256'] == sha(output / 'fpr-init.dol') == capture['harnessSha256'].lower()
assert capture['emulatorSha256'].lower() == control['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
image = (output / 'fpr-init.dol').read_bytes()
assert generation['originalSha256'] == hashlib.sha256(original).hexdigest()
assert generation['patches'] == [] and image[256:len(original)] == original[256:]
assert generation['records'] == control_generation['records'] and capture['records'] == 16
assert capture['accurateCache'] == 'True'
for flag in ('Dolphin.Core.CPUCore=0', 'Dolphin.Core.SerialPort1=255', '-v Null', 'dolphin-uart-ee-user'):
    assert flag in capture['arguments']
data, old = base64.b64decode(capture['data']), base64.b64decode(control['data'])
assert len(data) == len(old) == 16 * 736

def compare(payload):
    for index in range(16):
        row = payload[index * 736:(index + 1) * 736]
        expected = bytearray(old[index * 736:(index + 1) * 736])
        assert struct.unpack_from('>I', expected, 44)[0] == 0x2032
        struct.pack_into('>I', expected, 44, 0xa032)
        assert row[:144] == expected[:144] and row[640:656] == expected[640:656] and row[704:712] == expected[704:712]
        assert row[144:640] == bytes(496)

compare(data)
for index in range(16):
    changed = bytearray(data)
    changed[index * 736 + 24] ^= 1
    try:
        compare(changed)
    except AssertionError:
        continue
    raise AssertionError('Corrupted return accepted')
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_UNPATCHED_UART16_EEA032_MATCHES_RI2032_ENDPOINTS',
    'generatorSha256': sha(output / 'generation.json'), 'captureSha256': sha(output / 'fpr-init-true-dolphin.json'),
    'controlProofSha256': sha(private / 'dolphin-uart-ri/comparison.json'), 'verifierSha256': sha(Path(__file__)),
    'negativeCases': 16, 'limits': ['Prepared whole EUART/EXISync; only endpoint MSREE differs. No original instruction patches.',
        'No chronological IRQ/physical Wii/STM coexistence/full retail startup proof.']}, indent=2) + '\n')
print('PASS original unpatched UART16 EE=A032 endpoints; 16 corrupt returns rejected')

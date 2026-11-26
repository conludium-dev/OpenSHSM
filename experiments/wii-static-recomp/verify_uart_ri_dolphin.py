"""Compare unpatched UART with RI to the retained unpatched RI-off control."""
from pathlib import Path
import base64
import hashlib
import json
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'dolphin-uart-ri'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_uart_dolphin.py')], check=True)
generation = json.loads((output / 'generation.json').read_text())
capture = json.loads((output / 'fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
control_generation = json.loads((private / 'dolphin-uart-unobserved/generation.json').read_text())
control = json.loads((private / 'dolphin-uart-unobserved/fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
assert generation['generatorSha256'] == sha(experiment / 'build_uart_ri_dolphin.py')
assert generation['riParentSha256'] == sha(experiment / 'build_uart_unobserved_dolphin.py')
assert generation['wrapperSha256'] == sha(experiment / 'run_uart_ri_dolphin.ps1') == capture['scriptSha256'].lower()
assert generation['harnessSha256'] == sha(output / 'fpr-init.dol') == capture['harnessSha256'].lower()
assert capture['emulatorSha256'].lower() == control['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
image = (output / 'fpr-init.dol').read_bytes()
assert generation['originalSha256'] == hashlib.sha256(original).hexdigest()
assert generation['patches'] == [] and image[256:len(original)] == original[256:]
assert generation['records'] == control_generation['records'] and capture['records'] == 16
assert capture['accurateCache'] == 'True'
for flag in ('Dolphin.Core.CPUCore=0', 'Dolphin.Core.SerialPort1=255', '-v Null', 'dolphin-uart-ri-user'):
    assert flag in capture['arguments']
data, old = base64.b64decode(capture['data']), base64.b64decode(control['data'])
assert len(data) == len(old) == 16 * 736
for index in range(16):
    row = data[index * 736:(index + 1) * 736]
    expected = bytearray(old[index * 736:(index + 1) * 736])
    assert struct.unpack_from('>I', expected, 44)[0] == 0x2030
    struct.pack_into('>I', expected, 44, 0x2032)
    assert row[:144] == expected[:144] and row[640:656] == expected[640:656] and row[704:712] == expected[704:712]
    assert row[144:640] == bytes(496)
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_UNPATCHED_UART16_RI2032_MATCHES_RI2030_ENDPOINTS',
    'generatorSha256': sha(output / 'generation.json'), 'captureSha256': sha(output / 'fpr-init-true-dolphin.json'),
    'controlProofSha256': sha(private / 'dolphin-uart/comparison.json'), 'verifierSha256': sha(Path(__file__)),
    'limits': ['Whole original EUART/EXI, prepared1..4byte payload/init/NI/EXTINT fixture; MSR bit2only differs.',
        'Final snapshots, no new chronological interrupt/physical Wii/full-game proof.']}, indent=2) + '\n')
print('PASS16unpatched whole UART calls with RI2032 match RI2030control except disclosed MSR bit2')

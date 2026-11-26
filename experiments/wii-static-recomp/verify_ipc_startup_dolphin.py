"""Check unpatched whole IPC helper ABI/control/PI state with EE/RI enabled."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-ipc-startup')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
for key, name in [('generatorSha256', 'build_ipc_startup_dolphin.py'), ('parentSha256', 'build_si_query_dolphin.py'),
        ('helperSha256', 'build_dolphin_probe.py'), ('wrapperSha256', 'run_ipc_startup_dolphin.ps1'), ('baseRunnerSha256', 'run_dolphin_probe.ps1')]:
    assert generation[key] == sha(experiment / name)
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
image = (output / 'fpr-init.dol').read_bytes()
assert generation['originalSha256'] == hashlib.sha256(original).hexdigest()
assert generation['harnessSha256'] == sha(output / 'fpr-init.dol') == capture['harnessSha256'].lower()
assert capture['scriptSha256'].lower() == generation['wrapperSha256']
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
assert generation['patches'] == [] and image[256:len(original)] == original[256:]
assert capture['records'] == 16 and capture['accurateCache'] == 'True'
for flag in ('Dolphin.Core.CPUCore=0', '-v Null', 'dolphin-ipc-startup-user'):
    assert flag in capture['arguments']
data = base64.b64decode(capture['data'])
assert len(data) == 16 * 736
def check(row, case):
    assert row[:16] == b'OSHSM_PPC_DLP001'
    assert struct.unpack_from('>2I', row, 16) == (0xc001cafe, case['index'])
    fields = list(struct.unpack_from('>13I', row, 24))
    assert fields == [0, 0x10000, 4, 0xcd000000, 0x38, 0x80540000, 0x805335e0, 0x8052e720,
        case['return'], 0xa032, 0x38, 0x10000, 0x40f8], fields
    return fields
states = [check(data[i * 736:(i + 1) * 736], case) for i, case in enumerate(generation['records'])]
for offset in (32, 60, 64, 68):
    row = bytearray(data[:736])
    row[offset] ^= 1
    try:
        check(row, generation['records'][0])
    except AssertionError:
        pass
    else:
        raise AssertionError('Original IPC ABI/MSR/control/PI mutant accepted')
ghidra_dir = Path('work/private-game/static-recomp/ipc-sdk-roots/ghidra')
ghidra = json.loads((ghidra_dir / 'verification.json').read_text())
record = next(row for row in ghidra['records'] if row['name'] == 'IPCWriteReg')
assert record['assemblySha256'] == sha(ghidra_dir / 'IPCWriteReg.asm')
assert record['decompiledSha256'] == sha(ghidra_dir / 'IPCWriteReg.c')
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_IPC_COLD38_EE_RI16_HELPER_ABI_CONTROL_PI_PASS',
    'generationSha256': sha(output / 'generation.json'), 'captureSha256': sha(capture_path),
    'verifierSha256': sha(Path(__file__)), 'states': states, 'ghidraRecord': record,
    'limits': generation['limits'] + ['Dolphin PI reset-button level10000, not physical console.',
        'Cold no-request control projection only; no full client initialization or IPC interrupt/request timing.']}, indent=2) + '\n')
print('PASS16whole original cold control0→38 withA032/PI-mask40F8/ABI/PI unchanged/Ghidra')

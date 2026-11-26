"""Validate original arithmetic capture provenance/operands/lanes; native arithmetic remains pending."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-single-arithmetic')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert generation['generatorSha256'] == sha(experiment / 'build_single_arithmetic_dolphin.py')
assert generation['parentGeneratorSha256'] == sha(experiment / 'build_fcmp_dolphin.py')
assert generation['helperSha256'] == sha(experiment / 'build_dolphin_probe.py')
assert generation['baseRunnerSha256'] == sha(experiment / 'run_dolphin_probe.ps1')
assert generation['wrapperSha256'] == capture['scriptSha256'].lower() == sha(experiment / 'run_single_arithmetic_dolphin.ps1')
assert generation['harnessSha256'] == capture['harnessSha256'].lower() == sha(output / 'fpr-init.dol')
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert generation['originalSha256'] == hashlib.sha256(original).hexdigest()
image = (output / 'fpr-init.dol').read_bytes()
allowed = {i for offset in generation['patchOffsets'] for i in range(offset,offset + 4)}
assert {i for i in range(256,len(original)) if image[i] != original[i]} <= allowed
assert [image[offset - 4:offset].hex() for offset in generation['patchOffsets']] == ['ec220824','ec000072']
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
assert capture['records'] == len(generation['records']) == 2048 and capture['accurateCache'] == 'True'
data = base64.b64decode(capture['data'])
assert len(data) == 2048 * 736


def check(row,record):
    destination = 1 if record['operation'] == 0 else 0
    preserved = 2 if record['operation'] == 0 else 1
    value = record['a'] if record['operation'] == 0 else record['b']
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I',row,16) == (0xc001cafe,record['index'])
    assert struct.unpack_from('>Q',row,24)[0] & 0xffffffff == record['initialFpscr'] | record['ni'] * 4
    assert struct.unpack_from('>I',row,160)[0] == record['initialCr']
    assert struct.unpack_from('>Q',row,192 + destination * 8)[0] == struct.unpack_from('>Q',row,448 + destination * 8)[0]
    assert struct.unpack_from('>Q',row,192 + preserved * 8)[0] == value
    assert struct.unpack_from('>Q',row,448 + preserved * 8)[0] == 0x4008000000000000
    assert struct.unpack_from('>Q',row,704)[0] & 4 == record['ni'] * 4


mutants = 0
for record in generation['records']:
    row = data[record['index'] * 736:(record['index'] + 1) * 736]
    check(row,record)
    destination = 1 if record['operation'] == 0 else 0
    preserved = 2 if record['operation'] == 0 else 1
    for offset in (28,160,192 + destination * 8,448 + destination * 8,192 + preserved * 8,448 + preserved * 8,711):
        bad = bytearray(row)
        bad[offset] ^= 4 if offset == 711 else 1
        try:
            check(bad,record)
        except AssertionError:
            mutants += 1
        else:
            raise AssertionError('Unchecked arithmetic capture field')
assert mutants == 14336
(output / 'capture-verification.json').write_text(json.dumps({'result':'ORIGINAL_FDIVS_FMULS2048_CAPTURE_PROVENANCE_LANES_VALIDATED_NATIVE_PENDING',
    'verifierSha256':sha(Path(__file__)),'captureSha256':sha(capture_path),'generationSha256':sha(output / 'generation.json'),
    'records':2048,'mutants':mutants,'limits':['Actual original instructions, two adjacent observer exits only; synthetic IEEE/NI/status inputs.',
        'Provenance/pre-status/CR/paired result equality/unchanged other operand and lane checked, not arithmetic algorithm/native equivalence.',
        'Complete result/FPSCR bytes retained for later native comparison; no whole initializer or physical Wii claim.']},indent=2) + '\n')
print('PASS original arithmetic2048 capture/provenance/pre-status/CR/lanes/14336 mutations; native algorithms pending')

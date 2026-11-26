"""Verify original ordered comparison CR/FPSCR and unchanged operands/paired lanes."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-fcmp')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert generation['generatorSha256'] == sha(experiment / 'build_fcmp_dolphin.py')
assert generation['helperSha256'] == sha(experiment / 'build_dolphin_probe.py')
assert generation['baseRunnerSha256'] == sha(experiment / 'run_dolphin_probe.ps1')
assert generation['wrapperSha256'] == capture['scriptSha256'].lower() == sha(experiment / 'run_fcmp_dolphin.ps1')
assert generation['harnessSha256'] == capture['harnessSha256'].lower() == sha(output / 'fpr-init.dol')
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert generation['originalSha256'] == hashlib.sha256(original).hexdigest()
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
image = (output / 'fpr-init.dol').read_bytes()
offset = generation['patchOffset']
assert image[256:offset] == original[256:offset] and image[offset + 4:len(original)] == original[offset + 4:]
assert image[offset - 4:offset] == bytes.fromhex('fc010040')
assert capture['records'] == len(generation['records']) == 1024 and capture['accurateCache'] == 'True'
data = base64.b64decode(capture['data'])
assert len(data) == 1024 * 736


def expected(record):
    a,b = record['a'],record['b']
    magnitude = lambda bits: bits & 0x7fffffffffffffff
    nan = lambda bits: magnitude(bits) > 0x7ff0000000000000
    snan = lambda bits: nan(bits) and not bits & 0x8000000000000
    fpscr = record['initialFpscr'] | record['ni'] * 4
    if nan(a) or nan(b):
        cc = 1
        fpscr |= 0xa0080000 | (0x01000000 if snan(a) or snan(b) else 0)
    elif a == b or not (magnitude(a) | magnitude(b)):
        cc = 2
    elif (a >> 63) != (b >> 63):
        cc = 8 if a >> 63 else 4
    else:
        less = magnitude(a) > magnitude(b) if a >> 63 else magnitude(a) < magnitude(b)
        cc = 8 if less else 4
    return (record['initialCr'] & 0x0fffffff) | (cc << 28),fpscr | (cc << 12)


def check(row,record):
    assert row[:16] == b'OSHSM_PPC_DLP001'
    assert struct.unpack_from('>2I',row,16) == (0xc001cafe,record['index'])
    assert struct.unpack_from('>Q',row,24)[0] & 0xffffffff == record['initialFpscr'] | record['ni'] * 4
    assert struct.unpack_from('>I',row,160)[0] == expected(record)[0]
    assert struct.unpack_from('>Q',row,704)[0] & 0xffffffff == expected(record)[1]
    assert struct.unpack_from('>2Q',row,192) == (record['b'],record['a'])
    assert struct.unpack_from('>2Q',row,448) == (0x4008000000000000,0x4008000000000000)


mutants = 0
for record in generation['records']:
    row = data[record['index'] * 736:(record['index'] + 1) * 736]
    check(row,record)
    for position in (28,160,708,192,200,448,456):
        bad = bytearray(row)
        bad[position] ^= 1
        try:
            check(bad,record)
        except AssertionError:
            mutants += 1
        else:
            raise AssertionError('Unchecked comparison evidence mutation')
assert mutants == 7168
(output / 'comparison.json').write_text(json.dumps({'result':'DOLPHIN_FCMPO1024_CAPTURE_VALIDATED_FPCC_OR_DISCREPANCY_UNRESOLVED',
    'verifierSha256':sha(Path(__file__)),'captureSha256':sha(capture_path),'generationSha256':sha(output / 'generation.json'),
    'cases':1024,'mutantsRejected':mutants,'limits':['Exact original fcmpo cr0,f1,f0 only; NI0/NI1/two disabled-exception status profiles.',
        'Pre-instruction FPSCR matches fixture. Measured FPCC ORs prior GT rather than clearing it; disagrees with inspected Dolphin master source. Do not treat this inferred capture rule as physical Wii semantics.',
        'No enabled FP exception/other compare forms/whole enclosing function/native integration/physical Wii proof.']},indent=2) + '\n')
print('PASS capture fcmpo1024/pre-FPSCR/CR/NI/IEEE/lanes/7168 mutations; FPCC OR discrepancy unresolved, no native admission')

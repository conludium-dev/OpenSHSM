"""Validate the complete original function, outputs, lanes and preserved status."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'dolphin-fp-initializer'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation_path = output / 'generation.json'
generation = json.loads(generation_path.read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert capture['records'] == len(generation['records']) == 128 and capture['accurateCache'] == 'True'
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / 'run_fp_initializer_dolphin.ps1')
assert generation['generatorSha256'] == sha(experiment / 'build_fp_initializer_dolphin.py')
assert generation['helperSha256'] == sha(experiment / 'build_dolphin_probe.py')
assert generation['baseRunnerSha256'] == sha(experiment / 'run_dolphin_probe.ps1')
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
source = Path('work/private-game/disc/DATA/sys/main.dol')
assert generation['originalSha256'] == sha(source)
original, image = source.read_bytes(),(output / 'fpr-init.dol').read_bytes()
assert image[256:len(original)] == original[256:]
proof = json.loads((root / 'fp-initializer-source/ghidra/verification.json').read_text())
assert [(row['instructions'],row['bytes'],row['discoveredBodyBytes']) for row in proof['records']] == [(14,56,56)]
data = base64.b64decode(capture['data'])
assert len(data) == 128 * 736


def expected(record):
    value = record['value']
    single = struct.unpack('>I',struct.pack('>f',float(value)))[0]
    rounded = struct.unpack('>f',struct.pack('>I',single))[0]
    double = struct.unpack('>Q',struct.pack('>d',rounded))[0]
    classify = 2 if value == 0 else 8 if value < 0 else 4
    fpscr = ((record['initialFpscr'] | record['ni'] * 4) & ~0x1f000) | classify << 12
    return single,value & 0xffffffff,double,fpscr


def check(row,record):
    single,integer,double,fpscr = expected(record)
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I',row,16) == (0xc001cafe,record['index'])
    assert struct.unpack_from('>2I',row,24) == (single,integer)
    assert struct.unpack_from('>Q',row,192)[0] == struct.unpack_from('>Q',row,448)[0] == double
    assert struct.unpack_from('>Q',row,200)[0] == 0x4330000080000000
    assert struct.unpack_from('>Q',row,456)[0] == 0x4008000000000000
    assert struct.unpack_from('>Q',row,704)[0] & 0xffffffff == fpscr
    assert struct.unpack_from('>I',row,36)[0] == 0x80540000
    assert struct.unpack_from('>I',row,32)[0] == integer


mutants = 0
for record in generation['records']:
    row = data[record['index'] * 736:(record['index'] + 1) * 736]
    check(row,record)
    for offset in (24,28,192,200,448,456,708,36,32):
        bad = bytearray(row)
        bad[offset] ^= 1
        try:
            check(bad,record)
        except AssertionError:
            mutants += 1
        else:
            raise AssertionError('Unchecked initializer evidence mutation')
assert mutants == 1152
(output / 'comparison.json').write_text(json.dumps({'result':'WHOLE_ORIGINAL_SIGNED_INT_INITIALIZER128_RESULT_LANES_FPSCR_STACK_MATCH',
    'verifierSha256':sha(Path(__file__)),'generationSha256':sha(generation_path),'captureSha256':sha(capture_path),
    'ghidraProofSha256':sha(root / 'fp-initializer-source/ghidra/verification.json'),
    'cases':128,'mutantsRejected':mutants,
    'limits':['Whole original14 instructions unchanged; signed-int fixtures/NI0-NI1/two initial FPSCR controls.',
        'Observed rounding updates FPRF only, preserves sticky FI/FR/exception bits; not general fsubs/physical Wii semantics.',
        'SDA globals verified by whole execution, not collapsed Ghidra aliases; native current value528 measured separately.',
        'No native pending OPEN/IRQ/fullgame or first screen claim.']},indent=2) + '\n')
print('PASS128 whole original initializer/rounded float+saved int/both lanes/FPSCR preserved/stack/1152 mutations')

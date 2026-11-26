"""Check provenance, complete original span and captured store/register/return invariants."""
from pathlib import Path
import hashlib
import base64
import struct
import json

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'dolphin-divide-initializer'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert capture['records'] == len(generation['records']) == 128 and capture['accurateCache'] == 'True'
assert generation['generatorSha256'] == sha(experiment / 'build_divide_initializer_dolphin.py')
assert generation['helperSha256'] == sha(experiment / 'build_dolphin_probe.py')
assert generation['baseRunnerSha256'] == sha(experiment / 'run_dolphin_probe.ps1')
assert generation['wrapperSha256'] == capture['scriptSha256'].lower() == sha(experiment / 'run_divide_initializer_dolphin.ps1')
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert generation['originalSha256'] == hashlib.sha256(original).hexdigest()
image = (output / 'fpr-init.dol').read_bytes()
assert image[256:len(original)] == original[256:]
assert generation['harnessSha256'] == capture['harnessSha256'].lower() == sha(output / 'fpr-init.dol')
assert generation['function'] == 0x8013b0c0 and generation['functionBytes'] == 20
proof = json.loads((root / 'divide-initializer-source/ghidra/verification.json').read_text())
assert [(row['instructions'], row['bytes'], row['discoveredBodyBytes']) for row in proof['records']] == [(5, 20, 20)]
header = struct.unpack('>64I', original[:256])
section = next(i for i in range(18) if header[18 + i] <= 0x8052d3e0 < header[18 + i] + header[36 + i])
offset = header[section] + 0x8052d3e0 - header[18 + section]
numerator = struct.unpack_from('>I', original, offset)[0]


def expand(single):
    return struct.unpack('>Q', struct.pack('>d', struct.unpack('>f', struct.pack('>I', single))[0]))[0]


data = base64.b64decode(capture['data'])
assert len(data) == 128 * 736


def check(row, record):
    assert row[:16] == b'OSHSM_PPC_DLP001'
    assert struct.unpack_from('>2I', row, 16) == (0xc001cafe, record['index'])
    stored, neighbor = struct.unpack_from('>2I', row, 24)
    assert neighbor == 0xa5a5a5a5
    assert struct.unpack_from('>Q', row, 192)[0] == struct.unpack_from('>Q', row, 448)[0] == expand(stored)
    assert struct.unpack_from('>Q', row, 200)[0] == struct.unpack_from('>Q', row, 456)[0] == expand(numerator)
    assert struct.unpack_from('>Q', row, 704)[0] & 4 == record['ni'] * 4
    assert struct.unpack_from('>I', row, 36)[0] == 0x80540000


mutants = 0
for record in generation['records']:
    row = data[record['index'] * 736:(record['index'] + 1) * 736]
    check(row, record)
    for position in (24, 28, 192, 448, 200, 456, 711, 36):
        bad = bytearray(row)
        bad[position] ^= 4 if position == 711 else 1
        try:
            check(bad, record)
        except AssertionError:
            mutants += 1
        else:
            raise AssertionError('Unchecked whole-function capture invariant')
assert mutants == 1024
(output / 'capture-verification.json').write_text(json.dumps({'result': 'ORIGINAL_WHOLE_DIVIDE5_CAPTURE128_VALIDATED_NATIVE_PENDING',
    'verifierSha256': sha(Path(__file__)), 'captureSha256': sha(capture_path), 'ghidraProofSha256': sha(root / 'divide-initializer-source/ghidra/verification.json'),
    'numeratorBits': numerator, 'cases': 128, 'mutants': mutants,
    'limits': ['Original body unchanged, Ghidra independently confirms span; not native arithmetic or physical Wii proof.']}, indent=2) + '\n')
print('PASS whole original divide5/capture128/store-register-stack invariants/1024 mutations')

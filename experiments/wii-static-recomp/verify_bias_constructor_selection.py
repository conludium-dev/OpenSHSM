"""Reject byte mismatch and plausible but different arithmetic prefixes before lowering."""
from pathlib import Path
import hashlib
import json
import re
import struct
from bias_constructor_lowering import select, lower

root = Path('work/private-game/static-recomp')
output = root / 'bias-constructor-selection'
output.mkdir(exist_ok=True)
fixture = output / 'fixture'
fixture.mkdir(exist_ok=True)
source = root / 'dtk-output/asm/auto_fn_80017480_text.s'
assembly = source.read_text()
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
target = fixture / source.name
target.write_text(assembly)
assert len(select(original, fixture)) == 1
rejected = 0
for old,new in [('3C 60 43 30','3C 60 43 31'),('80 8D 9E FC','80 8D 9E F8'),
    ('6C 84 80 00','6C 84 40 00'),('90 81 00 0C','90 81 00 10'),('94 21 FF F0','48 00 00 04')]:
    image = bytearray(original)
    matched = re.search(r'/\* [0-9A-F]+ ([0-9A-F]+)  ' + old,assembly)
    assert matched and assembly.count(old) == 1
    offset = int(matched[1],16)
    image[offset:offset + 4] = bytes.fromhex(new)
    target.write_text(assembly.replace(old,new))
    assert select(image,fixture) == []
    rejected += 1
target.write_text(assembly)
header = struct.unpack('>64I',original[:256])
section = next(i for i in range(18) if header[18+i] <= 0x8052b790 < header[18+i]+header[36+i])
offset = header[section] + 0x8052b790 - header[18+section]
image = bytearray(original)
image[offset + 7] ^= 1
assert select(image,fixture) == []
rejected += 1
image = bytearray(original)
image[0x134e8] ^= 1
try:
    select(image,fixture)
except AssertionError:
    rejected += 1
else:
    raise AssertionError('Unchecked original instruction byte')
assert target.read_text() == assembly and rejected == 7
sites = select(original,root / 'dtk-output/asm')
build = json.loads((root / 'mass-fp-registration-boot/build.json').read_text())
changed = 0
for row in build['records']:
    text,changes = lower(Path(row['source']).read_text(),original,sites)
    again,second = lower(text,original,sites)
    assert again == text and second == []
    changed += len(changes)
assert len(sites) == 91 and changed == 89
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'verification.json').write_text(json.dumps({'result':'BYTE_DATAFLOW_SELECTOR7_REFUSALS_89_IDEMPOTENT_LOWERINGS',
    'verifierSha256':sha(Path(__file__)),'loweringSha256':sha(Path('experiments/wii-static-recomp/bias_constructor_lowering.py')),
    'originalSha256':hashlib.sha256(original).hexdigest(),'sites':91,'newBodies':89,'refusals':7,
    'limits':['Synthetic mutated copies in private fixture; no original source modification.',
        'Static selector contracts, not91 original runtime function observations.']},indent=2) + '\n')
print('PASS selector7 byte/dataflow/constant refusals;91 matched/89 idempotent lowerings; original untouched')

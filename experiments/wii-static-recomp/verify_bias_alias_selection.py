"""Reject mismatched source bytes, dataflow and constants; require idempotent exact lowering."""
from pathlib import Path
import re
import struct
import json
import hashlib
from bias_alias_initializer_lowering import select, lower

root = Path('work/private-game/static-recomp')
output = root / 'bias-alias-selection'
fixture = output / 'fixture'
fixture.mkdir(parents=True, exist_ok=True)
source = root / 'dtk-output/asm/auto_fn_800D8DC4_text.s'
assembly = source.read_text()
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
target = fixture / source.name
target.write_text(assembly)
assert len(select(original, fixture)) == 1
rejected = 0
for address, word in ((0x800d8dc8, 0x3c004331), (0x800d8ddc, 0x6c804000),
        (0x800d8dd4, 0x808d9ef8), (0x800d8dec, 0x48000001), (0x800d8de4, 0x7c000378)):
    match = re.search(r'/\* ' + f'{address:08X}' + r' ([0-9A-F]+)  ((?:[0-9A-F]{2} ){3}[0-9A-F]{2}) \*/', assembly)
    assert match
    offset = int(match[1], 16)
    image = bytearray(original)
    encoded = struct.pack('>I', word)
    image[offset:offset + 4] = encoded
    target.write_text(assembly[:match.start(2)] + ' '.join(f'{byte:02X}' for byte in encoded) + assembly[match.end(2):])
    assert not select(image, fixture)
    rejected += 1
target.write_text(assembly)
header = struct.unpack('>64I', original[:256])
section = next(i for i in range(18) if header[18 + i] <= 0x8052ca18 < header[18 + i] + header[36 + i])
offset = header[section] + 0x8052ca18 - header[18 + section]
image = bytearray(original)
image[offset + 7] ^= 1
assert not select(image, fixture)
rejected += 1
match = re.search(r'/\* 800D8DF4 ([0-9A-F]+)', assembly)
image = bytearray(original)
image[int(match[1], 16)] ^= 1
try:
    select(image, fixture)
except AssertionError:
    rejected += 1
else:
    raise AssertionError('Unchecked later arithmetic source word')
sites = select(original, root / 'dtk-output/asm')
base = json.loads((root / 'mass-multiply-register-boot/build.json').read_text())
changes = []
for row in base['records']:
    text, changed = lower(Path(row['source']).read_text(), original, sites)
    again, second = lower(text, original, sites)
    assert text == again and not second
    changes.extend(changed)
assert rejected == 7 and len(changes) == 3
assert [change['address'] for change in changes] == [0x800d8df0, 0x800d8df4, 0x800d8df8]
assert target.read_text() == assembly
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'verification.json').write_text(json.dumps({'result': 'PASS_ALIAS_SELECTION7_IDEMPOTENT3',
    'verifierSha256': sha(Path(__file__)), 'loweringSha256': sha(Path(__file__).with_name('bias_alias_initializer_lowering.py')),
    'limits': ['Consistent private mutants only; static byte/dataflow validation is not whole-function behavior.']}, indent=2) + '\n')
print('PASS alias source/dataflow7 refusals/three exact lowerings/idempotence')

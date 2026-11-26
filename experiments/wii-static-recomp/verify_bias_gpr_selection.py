"""Reject corrupted provenance, stale GPR facts and unsupported producers."""
from pathlib import Path
import struct
import re
import json
import hashlib
from bias_gpr_producer_lowering import select, lower

root = Path('work/private-game/static-recomp')
output = root / 'bias-gpr-selection'
fixture = output / 'fixture'
fixture.mkdir(parents=True, exist_ok=True)
source = root / 'dtk-output/asm/auto_fn_8017ACE8_text.s'
assembly = source.read_text()
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
target = fixture / source.name
target.write_text(assembly)
assert [site['address'] for site in select(original, fixture)] == [0x8017ad30]
refused = 0
for address, word in ((0x8017acf0, 0x3cc04331), (0x8017ad18, 0x6ca04000),
        (0x8017ad08, 0x80ad9ef8), (0x8017ad14, 0x7ca02896),
        (0x8017ad14, 0x7c802a14), (0x8017ad2c, 0x48000001)):
    match = re.search(r'/\* ' + f'{address:08X}' + r' ([0-9A-F]+)  ((?:[0-9A-F]{2} ){3}[0-9A-F]{2}) \*/', assembly)
    assert match
    image = bytearray(original)
    encoded = struct.pack('>I', word)
    offset = int(match[1], 16)
    image[offset:offset + 4] = encoded
    target.write_text(assembly[:match.start(2)] + ' '.join(f'{byte:02X}' for byte in encoded) + assembly[match.end(2):])
    assert not select(image, fixture)
    refused += 1
target.write_text(assembly)
header = struct.unpack('>64I', original[:256])
section = next(i for i in range(18) if header[18 + i] <= 0x8052dc60 < header[18 + i] + header[36 + i])
offset = header[section] + 0x8052dc60 - header[18 + section]
image = bytearray(original)
image[offset + 7] ^= 1
assert not select(image, fixture)
refused += 1
image = bytearray(original)
image[0x176d70] ^= 1
try:
    select(image, fixture)
except AssertionError:
    refused += 1
else:
    raise AssertionError('Unchecked original instruction mismatch')
sites = select(original, root / 'dtk-output/asm')
assert len(sites) == 96
build = json.loads((root / 'mass-divide-initializer-boot/build.json').read_text())
changes = []
for row in build['records']:
    text, changed = lower(Path(row['source']).read_text(), original, sites)
    again, second = lower(text, original, sites)
    assert again == text and not second
    changes.extend(changed)
assert refused == 8 and len(changes) == 1 and changes[0]['address'] == 0x8017ad30
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'verification.json').write_text(json.dumps({'result': 'PASS_GPR_SELECTION8_ONE_IDEMPOTENT_LOWERING',
    'verifierSha256': sha(Path(__file__)), 'loweringSha256': sha(Path(__file__).with_name('bias_gpr_producer_lowering.py')),
    'limits': ['Known GPR-only producers invalidate destinations; no inferred arithmetic values or second input/6 site admitted.']}, indent=2) + '\n')
print('PASS GPR producer/dataflow8 refusals/96static sites/one new idempotent lowering')

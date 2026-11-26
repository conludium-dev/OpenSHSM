"""Reject stale pre-call facts, altered operands and unsupported producers."""
from pathlib import Path
import re
import struct
import hashlib
import json
from bias_block_lowering import select, lower

root = Path('work/private-game/static-recomp')
output = root / 'bias-block-selection'
fixture = output / 'fixture'
fixture.mkdir(parents=True,exist_ok=True)
source = root / 'dtk-output/asm/auto_fn_800BB1BC_text.s'
assembly = source.read_text()
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
target = fixture / source.name
target.write_text(assembly)
assert any(site['address'] == 0x800bb268 and site['boundary'] == 'after-call' for site in select(original,fixture))
rejected = 0
for address,word in [(0x800bb250,0x3c004331),(0x800bb258,0x6c604000),(0x800bb24c,0x806d9ef8),
    (0x800bb264,0x48000001),(0x800bb260,0x7c000378)]:
    match = re.search(r'/\* ' + f'{address:08X}' + r' ([0-9A-F]+)  ((?:[0-9A-F]{2} ){3}[0-9A-F]{2}) \*/',assembly)
    assert match
    offset = int(match[1],16)
    image = bytearray(original)
    image[offset:offset + 4] = struct.pack('>I',word)
    encoded = ' '.join(f'{byte:02X}' for byte in struct.pack('>I',word))
    target.write_text(assembly[:match.start(2)] + encoded + assembly[match.end(2):])
    assert not any(site['address'] == 0x800bb268 for site in select(image,fixture))
    rejected += 1
target.write_text(assembly)
image = bytearray(original)
mutated = assembly
for address,word in [(0x800bb268,0x48000001),(0x800bb26c,0xec000828)]:
    match = re.search(r'/\* ' + f'{address:08X}' + r' ([0-9A-F]+)  ((?:[0-9A-F]{2} ){3}[0-9A-F]{2}) \*/',mutated)
    assert match
    offset = int(match[1],16)
    image[offset:offset + 4] = struct.pack('>I',word)
    encoded = ' '.join(f'{byte:02X}' for byte in struct.pack('>I',word))
    mutated = mutated[:match.start(2)] + encoded + mutated[match.end(2):]
target.write_text(mutated)
assert not any(site['address'] == 0x800bb26c for site in select(image,fixture))
rejected += 1
target.write_text(assembly)
header = struct.unpack('>64I',original[:256])
section = next(i for i in range(18) if header[18+i] <= 0x8052c5a0 < header[18+i]+header[36+i])
offset = header[section] + 0x8052c5a0 - header[18+section]
image = bytearray(original)
image[offset + 7] ^= 1
assert not any(site['address'] == 0x800bb268 for site in select(image,fixture))
rejected += 1
image = bytearray(original)
image[0xb72a8] ^= 1
try:
    select(image,fixture)
except AssertionError:
    rejected += 1
else:
    raise AssertionError('Unchecked original byte mismatch')
assert rejected == 8 and target.read_text() == assembly
sites = select(original,root / 'dtk-output/asm')
build = json.loads((root / 'mass-single-arithmetic-boot/build.json').read_text())
changes = []
for row in build['records']:
    text,changed = lower(Path(row['source']).read_text(),original,sites)
    again,second = lower(text,original,sites)
    assert again == text and second == []
    changes.extend(changed)
assert len(sites) == 92 and len(changes) == 1 and changes[0]['address'] == 0x800bb268
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'verification.json').write_text(json.dumps({'result':'AFTER_CALL_BYTE_DATAFLOW8_REFUSALS_ONE_IDEMPOTENT_NEW_SITE',
    'verifierSha256':sha(Path(__file__)),'selectorSha256':sha(Path('experiments/wii-static-recomp/bias_block_lowering.py')),
    'parentSelectorSha256':sha(Path('experiments/wii-static-recomp/bias_constructor_lowering.py')),
    'sites':92,'newSites':1,'refusals':8,'limits':['Calls/control branches reset register/float/stack facts; unsupported producers disable tracking until the next control boundary.',
        'SDA/stack ABI assumptions are static inference; existing runtime checks actual operand bits/profile before mutation.',
        'Synthetic private mutant copies only, not full constructor or hardware verification.']},indent=2) + '\n')
print('PASS block selector8 stale-call/producer/operand/constant/byte refusals;92 sites/one new/idempotent')

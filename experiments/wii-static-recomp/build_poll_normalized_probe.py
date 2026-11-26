"""Normalize the two observed startup low-memory inputs, retaining the raw measurement."""
from pathlib import Path
import hashlib
import json
import struct

root = Path('work/private-game/static-recomp')
base = root / 'dolphin-poll-probe'
output = root / 'dolphin-poll-normalized-probe'
output.mkdir(exist_ok=True)
experiment = Path('experiments/wii-static-recomp')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
original = original_path.read_bytes()
assert hashlib.sha1(original).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
image = (base / 'boot.dol').read_bytes()
prior = struct.unpack('>64I', image[:256])
text = next(i for i in range(7) if prior[18 + i] == 0x80600000)
words = list(struct.unpack('>' + 'I' * (prior[36 + text] // 4), image[prior[text]:prior[text] + prior[36 + text]]))
index = next(i for i, op in enumerate(words) if op >> 26 == 18 and not op & 3
             and 0x80600000 + i * 4 + ((op & 0x03fffffc) - (0x04000000 if op & 0x02000000 else 0)) == 0x80006310)
seed = []
for offset in (0x34, 0xf4):
    seed += [(15 << 26) | (11 << 21) | 0xc000, (24 << 26) | (11 << 21) | (11 << 16) | offset,
             (36 << 26) | (11 << 16), (31 << 26) | (11 << 11) | (470 << 1)]
seed += [(14 << 26) | (11 << 21)]
words[index:index] = seed
branch_address = 0x80600000 + (index + len(seed)) * 4
words[index + len(seed)] = (18 << 26) | ((0x80006310 - branch_address) & 0x03fffffc)
collector = branch_address + 4
packed = struct.pack('>' + 'I' * len(words), *words)
data_index = next(i for i in range(7, 18) if prior[18 + i] == 0x80002000)
data = image[prior[data_index]:prior[data_index] + prior[36 + data_index]]
header = list(struct.unpack('>64I', original[:256]))
new = bytearray(original)
for slot, address, content in [(text, 0x80600000, packed), (data_index, 0x80002000, data)]:
    assert header[36 + slot] == 0
    header[slot], header[18 + slot], header[36 + slot] = len(new), address, len(content)
    new.extend(content)
endpoint = 0x8021c000
slot = next(i for i in range(18) if header[18 + i] <= endpoint < header[18 + i] + header[36 + i])
offset = header[slot] + endpoint - header[18 + slot]
struct.pack_into('>I', new, offset, (18 << 26) | ((collector - endpoint) & 0x03fffffc))
header[56] = 0x80600000
new[:256] = struct.pack('>64I', *header)
(output / 'boot.dol').write_bytes(new)
report = json.loads((base / 'generation.json').read_text())
report.update({'harnessSha256': hashlib.sha256(new).hexdigest(), 'generatorSha256': sha(Path(__file__)),
               'wrapperSha256': sha(experiment / 'run_poll_normalized_probe.ps1'), 'collector': hex(collector),
               'baseMeasurementSha256': sha(base / 'boot.dol'), 'baseGenerationSha256': sha(base / 'generation.json'),
               'normalizedInputs': [{'address': hex(0x80000000 + offset), 'value': 0} for offset in (0x34, 0xf4)],
               'scope': 'Controlled zero low-memory startup inputs, not measured physical Wii boot environment.'})
(output / 'generation.json').write_text(json.dumps(report, indent=2) + '\n')
print('Generated separate normalized low-memory poll fixture; raw capture preserved')

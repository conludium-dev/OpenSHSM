"""Private conflict-set measurement with unchanged original DCEnable code."""
from pathlib import Path
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-conflict-probe')
output.mkdir(exist_ok=True)
source = Path('work/private-game/disc/DATA/sys/main.dol')
original = source.read_bytes()
assert hashlib.sha1(original).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = list(struct.unpack('>64I', original[:256]))
code = []
base = 0x80600000
stride = 736
data = bytearray(stride * 8)

def dform(op, reg, ra, value):
    return op << 26 | reg << 21 | ra << 16 | (value & 65535)

def pointer(reg, value):
    code.extend([dform(15, reg, 0, value >> 16), dform(24, reg, reg, value)])

def cache(address, op):
    pointer(4, address)
    code.append(31 << 26 | 4 << 11 | op << 1)

def access(address, value=None):
    pointer(4, address)
    if value is None:
        code.append(dform(32, 5, 4, 0))
    else:
        pointer(5, value)
        code.append(dform(36, 5, 4, 0))

code.extend([dform(14, 0, 0, 0x2030), 31 << 26 | 146 << 1])
pointer(1, 0x80540000)
code.append(31 << 26 | 0 << 21 | 16 << 16 | 31 << 11 | 467 << 1)
address = base + len(code) * 4
code.append(18 << 26 | ((0x80212f80 - address) & 0x03fffffc) | 1)
patterns = [[], [0], [7], [0, 1, 2, 3], [7, 6, 5, 4], [0, 2, 4, 6], [1, 3, 5, 7], [3, 3, 0, 7, 2]]
for case, touches in enumerate(patterns):
    data[case * stride:case * stride + 16] = b'OSHSM_PPC_DLP001'
    struct.pack_into('>I', data, case * stride + 20, case)
    # Distinct sets isolate trials; uncached observations do not touch replacement state.
    start = 0x80680000 + case * 32
    for index in range(10):
        cache(start + index * 4096, 470)
        access((start + index * 4096) | 0x40000000, 0x1000 + index)
    for index in range(8):
        access(start + index * 4096, 0x2000 + index)
    for index in touches:
        access(start + index * 4096)
    access(start + 8 * 4096, 0x2008)
    pointer(12, 0xc0002000 + case * stride)
    for index in range(10):
        access((start + index * 4096) | 0x40000000)
        code.append(dform(36, 5, 12, 32 + index * 4))
    access(start + 9 * 4096, 0x2009)
    for index in range(10):
        access((start + index * 4096) | 0x40000000)
        code.append(dform(36, 5, 12, 72 + index * 4))
    pointer(5, 0xc001cafe)
    code.append(dform(36, 5, 12, 16))
here = base + len(code) * 4
code.append(18 << 26)
packed = struct.pack('>' + 'I' * len(code), *code)
image = bytearray(original)
text = next(index for index in range(7) if not header[36 + index])
section = next(index for index in range(7, 18) if not header[36 + index])
for index, virtual, content in [(text, base, packed), (section, 0x80002000, data)]:
    header[index], header[18 + index], header[36 + index] = len(image), virtual, len(content)
    image.extend(content)
header[56] = base
image[:256] = struct.pack('>64I', *header)
(output / 'fpr-init.dol').write_bytes(image)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = {'originalSha256': sha(source), 'harnessSha256': hashlib.sha256(image).hexdigest(),
          'patterns': patterns, 'records': 8, 'samplesPerRecord': 20,
          'generatorSha256': sha(Path(__file__)), 'baseRunnerSha256': sha(experiment / 'run_dolphin_probe.ps1'),
          'wrapperSha256': sha(experiment / 'run_conflict_probe.ps1'),
          'scope': 'Synthetic dirty conflict-set accesses around unchanged original DCEnable. No retail boot or physical Wii claim.'}
(output / 'generation.json').write_text(json.dumps(report, indent=2) + '\n')
print('Generated private eight-trial conflict-set DOL; original DCEnable unchanged')

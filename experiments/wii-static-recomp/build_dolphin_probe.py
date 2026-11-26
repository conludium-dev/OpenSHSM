"""Private DOL measurement adapters; retain original function bytes except a disclosed boot stop branch."""
from pathlib import Path
import argparse
import hashlib
import json
import struct

parser = argparse.ArgumentParser()
parser.add_argument('--icache', action='store_true')
parser.add_argument('--coherence', action='store_true')
args = parser.parse_args()
assert not (args.icache and args.coherence)
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
original = original_path.read_bytes()
assert hashlib.sha1(original).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = list(struct.unpack('>64I', original[:256]))
slot = next(index for index in range(7) if header[36 + index] == 0)
output = Path('work/private-game/static-recomp/dolphin-icache-probe' if args.icache else 'work/private-game/static-recomp/dolphin-probe')
if args.coherence:
    output = Path('work/private-game/static-recomp/dolphin-coherence-probe')
output.mkdir(exist_ok=True)
CODE = 0x80600000
RESULT = 0x2000
STRIDE = 736
MAGIC = b'OSHSM_PPC_DLP001'

def dform(op, reg, base, immediate):
    return (op << 26) | (reg << 21) | (base << 16) | (immediate & 65535)

def spr(reg, ident, write=False):
    return (31 << 26) | (reg << 21) | ((ident & 31) << 16) | ((ident >> 5) << 11) | ((467 if write else 339) << 1)

def branch(address, target, link=False):
    displacement = target - address
    assert displacement % 4 == 0 and -(1 << 25) <= displacement < (1 << 25)
    return (18 << 26) | (displacement & 0x03fffffc) | int(link)

def pointer(code, reg, value):
    code.extend([dform(15, reg, 0, value >> 16), dform(24, reg, reg, value & 65535)])

def capture(code, destination, uncached=False):
    code.append(spr(12, 275, True))
    pointer(code, 12, (0xc0000000 if uncached else 0x80000000) + destination)
    for reg in range(32):
        if reg != 12:
            code.append(dform(36, reg, 12, 32 + reg * 4))
    code.extend([spr(11, 275), dform(36, 11, 12, 32 + 12 * 4)])
    code.append((31 << 26) | (11 << 21) | (19 << 1))
    code.append(dform(36, 11, 12, 160))
    for offset, ident in [(164, 8), (168, 9), (172, 1), (176, 920), (180, 1008)]:
        code.extend([spr(11, ident), dform(36, 11, 12, offset)])
    code.extend([(31 << 26) | (11 << 21) | (83 << 1), dform(36, 11, 12, 184)])
    for reg in range(32):
        code.append(dform(54, reg, 12, 192 + reg * 8))
    code.extend([(63 << 26) | (583 << 1), dform(54, 0, 12, 704)])
    pointer(code, 11, 0xa0000000)
    code.append(spr(11, 920, True))
    for reg in range(32):
        code.extend([(4 << 26) | (reg << 16) | (reg << 11) | (624 << 1), dform(54, 0, 12, 448 + reg * 8)])
    pointer(code, 11, 0xc001cafe)
    code.append(dform(36, 11, 12, 16))

records = []
for name in (['boot'] if args.icache or args.coherence else ['boot', 'fpr-init']):
    code = []
    data = bytearray(STRIDE * (1 if name == 'boot' else 8))
    for index in range(len(data) // STRIDE):
        data[index * STRIDE:index * STRIDE + 16] = MAGIC
        struct.pack_into('>I', data, index * STRIDE + 20, index)
    # Original init-registers makes r13=8052E720; explicit fixtures use that same SDA base.
    if args.coherence:
        constants = struct.pack('>I', 0x11223344) + bytes(28)
        code.extend([dform(14, 0, 0, 0x2030), (31 << 26) | (146 << 1), dform(14, 0, 0, 0), spr(0, 1008, True)])
        pointer(code, 1, 0x80540000)
        pointer(code, 4, 0xc0618000)
        pointer(code, 0, 0x11223344)
        code.append(dform(36, 0, 4, 0))
        code.append(branch(CODE + len(code) * 4, 0x80212f80, True))
        pointer(code, 4, 0x80618000)
        pointer(code, 0, 0x55667788)
        code.extend([dform(36, 0, 4, 0), dform(32, 5, 4, 0)])
        pointer(code, 10, 0xc0618000)
        code.append(dform(32, 6, 10, 0))
        code.append((31 << 26) | (4 << 11) | (54 << 1))
        code.append(dform(32, 7, 10, 0))
        pointer(code, 0, 0x99aabbcc)
        code.extend([dform(36, 0, 10, 0), dform(32, 8, 4, 0)])
        code.append((31 << 26) | (4 << 11) | (470 << 1))
        code.append(dform(32, 9, 4, 0))
        capture(code, RESULT, uncached=True)
    elif name == 'fpr-init':
        constants = b''.join(struct.pack('>ff', float((index + 1) * (mode + 1)), -float((index + 1) * (mode + 1)))
                             for mode in range(8) for index in range(32))
        for mode in range(8):
            code.extend([dform(14, 0, 0, 0x2030), (31 << 26) | (0 << 21) | (146 << 1)])
            pointer(code, 3, 0xa0000000)
            code.append(spr(3, 920, True))
            code.extend([dform(14, 0, 0, 0), spr(0, 912, True)])
            pointer(code, 3, 0x80618000 + mode * 256)
            for reg in range(32):
                code.append(dform(56, reg, 3, reg * 8))
            pointer(code, 3, 0 if mode < 4 else 0xa0000000)
            code.append(spr(3, 920, True))
            code.extend([dform(14, 0, 0, 0x30), (31 << 26) | (146 << 1)])
            pointer(code, 13, 0x8052e720)
            code.append(branch(CODE + len(code) * 4, 0x80210890, True))
            capture(code, RESULT + mode * STRIDE)
    else:
        code.extend([dform(14, 0, 0, 0x2030), (31 << 26) | (146 << 1)])
        pointer(code, 3, 0xa0000000)
        code.append(spr(3, 920, True))
        pointer(code, 3, 0x8052aa50)
        code.append(dform(56, 0, 3, 0))
        for reg in range(1, 32):
            code.append((4 << 26) | (reg << 21) | (72 << 1))
        code.append(0xfdfe058e)
        for reg in range(32):
            code.append(dform(14, reg, 0, 0))
        code.extend([spr(0, 920, True), spr(0, 1008, True), spr(0, 8, True), spr(0, 9, True), spr(0, 1, True),
                     (31 << 26) | (255 << 12) | (144 << 1), dform(14, 0, 0, 0x30),
                     (31 << 26) | (146 << 1), dform(14, 0, 0, 0)])
        code.append(branch(CODE + len(code) * 4, 0x80006310))
        stop_target = CODE + len(code) * 4
        capture(code, RESULT)
    code.append(branch(CODE + len(code) * 4, CODE + len(code) * 4))
    while len(code) % 8:
        code.append(0x60000000)
    packed_code = struct.pack('>' + 'I' * len(code), *code)
    image = bytearray(original)
    updated = header.copy()
    updated[slot] = len(image)
    updated[18 + slot] = CODE
    updated[36 + slot] = len(packed_code)
    image.extend(packed_code)
    data_slot = next(index for index in range(7, 18) if header[36 + index] == 0)
    updated[data_slot] = len(image)
    updated[18 + data_slot] = 0x80000000 + RESULT
    updated[36 + data_slot] = len(data)
    image.extend(data)
    if name == 'fpr-init' or args.coherence:
        constant_slot = next(index for index in range(7, 18) if header[36 + index] == 0 and index != data_slot)
        updated[constant_slot] = len(image)
        updated[18 + constant_slot] = 0x80618000
        updated[36 + constant_slot] = len(constants)
        image.extend(constants)
    updated[56] = CODE
    image[:256] = struct.pack('>64I', *updated)
    patches = []
    if name == 'boot' and not args.coherence:
        address = 0x80212f8c if args.icache else 0x802130ec
        section = next(index for index in range(18) if header[18 + index] <= address < header[18 + index] + header[36 + index])
        offset = header[section] + address - header[18 + section]
        before = struct.unpack_from('>I', original, offset)[0]
        assert before == 0x7c70fba6
        after = branch(address, stop_target)
        struct.pack_into('>I', image, offset, after)
        patches.append({'address': hex(address), 'original': hex(before), 'measurementBranch': hex(after)})
    path = output / (name + '.dol')
    path.write_bytes(image)
    records.append({'file': path.name, 'sha256': hashlib.sha256(image).hexdigest(), 'patches': patches,
                    'records': len(data) // STRIDE, 'entry': hex(CODE), 'codeSha256': hashlib.sha256(packed_code).hexdigest()})
report = {'originalSha256': hashlib.sha256(original).hexdigest(), 'records': records, 'stride': STRIDE,
          'resultPhysicalAddress': RESULT, 'scriptSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'scope': 'Private measurement harness, not an unmodified retail startup or replacement game binary.'}
(output / 'generation.json').write_text(json.dumps(report, indent=2) + '\n')
print('Generated private Dolphin measurement DOLs; original copy unchanged')

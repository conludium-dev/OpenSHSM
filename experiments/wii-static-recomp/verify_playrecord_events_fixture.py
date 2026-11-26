"""Verify the private observer ISA before any live callback interpretation."""
from pathlib import Path
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'dolphin-playrecord-events'
report = json.loads((output / 'generation.json').read_text())
image = (output / 'fpr-init.dol').read_bytes()
original = (root / 'dolphin-playrecord-start/fpr-init.dol').read_bytes()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert report['generatorSha256'] == sha(experiment / 'build_playrecord_events_dolphin.py')
assert report['replayParentSha256'] == sha(experiment / 'build_sysconf_events_dolphin.py')
assert report['wrapperSha256'] == sha(experiment / 'run_playrecord_events_disc_dolphin.ps1')
assert report['controlGenerationSha256'] == sha(root / 'dolphin-playrecord-start/generation.json')
assert report['harnessSha256'] == hashlib.sha256(image).hexdigest()
assert (report['eventAddress'], report['eventStride'], report['eventCapacity']) == (0x80740000, 1280, 256)
layout = struct.unpack('>64I', image[:256])
baseline = bytearray(original)


def words_at(address, count):
    slot = next(i for i in range(7) if layout[18 + i] <= address
        and address + count * 4 <= layout[18 + i] + layout[36 + i])
    return list(struct.unpack_from('>' + str(count) + 'I', image,
        layout[slot] + address - layout[18 + slot]))


def target(address, word):
    assert word >> 26 == 18 and not word & 3
    displacement = word & 0x3fffffc
    return address + displacement - (0x4000000 if displacement & 0x2000000 else 0)


def pointer(register, address):
    return [0x3c000000 | register << 21 | address >> 16,
        0x60000000 | register << 21 | register << 16 | address & 0xffff]


expected_sites = [(1, 0x80241c30, 0x5460103a), (2, 0x8021cde0, 0x9421ffe0),
    (3, 0x80240680, 0x9421fff0), (4, 0x80244e30, 0x9421fff0),
    (5, 0x802407d0, 0x2c1f0000), (6, 0x802438b0, 0x9421ffe0),
    (7, 0x80241e9c, 0x806da454)]
regions = [(64, 0x935e0080, 64), (128, 0xd35e0080, 64),
    (192, 0x935e00e0, 64), (256, 0xd35e00e0, 64), (320, 0x935e1020, 320),
    (640, 0x80493120, 128), (768, 0x804931d0, 140), (912, 0x8049325c, 144),
    (1056, 0x80528a40, 4), (1060, 0x8052ab40, 32), (1104, 0x804b2a80, 80),
    (1184, 0x80492658, 64), (1248, 0x80492260, 32)]
save = [0x9001ffe0, 0x9161ffe4, 0x9181ffe8, 0x7c000026, 0x9001ffec, 0x7c0000a6, 0x9001fff0]
restore = [0x8001ffec, 0x7c0ff120, 0x8161ffe4, 0x8181ffe8, 0x8001fff0, 0x7c000124, 0x8001ffe0]
index_code = [0x5580502a, 0x558c402e, 0x7d806214, 0x7d6b6214, 0x396b0040]
assert len(report['patches']) == len(expected_sites)
for patch, expected in zip(report['patches'], expected_sites):
    assert (patch['kind'], patch['address'], patch['opcode']) == expected
    address, offset = patch['address'], patch['offset']
    assert struct.unpack_from('>I', original, offset)[0] == patch['opcode']
    assert target(address, struct.unpack_from('>I', image, offset)[0]) == patch['trampoline']
    assert words_at(patch['trampoline'], len(save)) == save
    assert words_at(patch['restore'], len(restore)) == restore
    assert words_at(patch['end'] - 8, 1) == [patch['opcode']]
    assert target(patch['end'] - 4, words_at(patch['end'] - 4, 1)[0]) == address + 4
    span = words_at(patch['trampoline'], (patch['end'] - patch['trampoline']) // 4)
    start = next(i for i in range(len(span) - 4) if span[i:i + 5] == index_code)
    for count in range(256):
        regs = [0] * 32
        regs[11], regs[12] = 0xc0740000, count
        for word in span[start:start + 5]:
            op, rs, ra = word >> 26, (word >> 21) & 31, (word >> 16) & 31
            if op == 21:
                shift, mb, me = (word >> 11) & 31, (word >> 6) & 31, (word >> 1) & 31
                value = regs[rs]
                rotated = ((value << shift) | (value >> (32 - shift))) & 0xffffffff
                mask = sum(1 << (31 - bit) for bit in range(mb, me + 1))
                regs[ra] = rotated & mask
            elif op == 31:
                assert (word >> 1) & 1023 == 266
                regs[rs] = (regs[ra] + regs[(word >> 11) & 31]) & 0xffffffff
            else:
                assert op == 14
                regs[rs] = (regs[ra] + (word & 65535)) & 0xffffffff
        assert regs[11] == 0xc0740040 + count * 1280
    previous_end = 0
    for slot, source, size in regions:
        assert previous_end <= slot and slot + size <= 1280 and size % 4 == 0
        expected_copy = pointer(12, source)
        for index in range(0, size, 4):
            expected_copy += [0x800c0000 | index, 0x900b0000 | (slot + index)]
        assert any(span[i:i + len(expected_copy)] == expected_copy for i in range(len(span)))
        previous_end = slot + size
    struct.pack_into('>I', baseline, offset, struct.unpack_from('>I', image, offset)[0])
assert image[256:len(original)] == baseline[256:]
spans = [(layout[18 + i], layout[18 + i] + layout[36 + i]) for i in range(18) if layout[36 + i]]
if layout[57]:
    spans.append((layout[56], layout[56] + layout[57]))
for index, (start, end) in enumerate(spans):
    for other_start, other_end in spans[index + 1:]:
        assert end <= other_start or other_end <= start
print('PASS seven exact replay sites/save-restore/1792 stride cases/all13 snapshot copy sequences/no section-BSS overlap/other source bytes unchanged; no live callback claim')

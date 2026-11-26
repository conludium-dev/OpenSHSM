"""Measure original cache-line zeroing before and after original cache flush."""
from pathlib import Path
import hashlib
import json
import struct
experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_si_query_dolphin.py'
source = parent.read_text()
exec(compile(source[:source.index('for index in range(16):')].replace('dolphin-si-query', 'dolphin-dc-zero'), str(parent), 'exec'), globals())
data = bytearray(32 * stride)
code.extend([dform(14, 0, 0, 0x2032), (31 << 26) | (146 << 1)])
pointer(code, 0, 0xc200)
code.append(spr(0, 1008, True))
pointer(code, 1, 0x80540000)
pointer(code, 2, 0x805335e0)
pointer(code, 13, 0x8052e720)
code.append(branch(base + len(code) * 4, 0x8021a140, True))
for index in range(32):
    length = [0, 1, 31, 32, 33, 63, 64, 128][index % 8]
    address = 0x80550000 + (0 if index % 16 < 8 else 7)
    data[index * stride:index * stride + 16] = b'OSHSM_PPC_DLP001'
    struct.pack_into('>I', data, index * stride + 20, index)
    pointer(code, 30, 0xc0680000 + index * stride)
    pointer(code, 31, 0x55660000 + index)
    for offset in range(0, 160, 32):
        pointer(code, 11, 0x80550000 + offset)
        code.append((31 << 26) | (11 << 11) | (470 << 1))
    pointer(code, 11, 0xc0550000)
    pointer(code, 0, 0xa5a5a5a5)
    for offset in range(0, 160, 4):
        code.append(dform(36, 0, 11, offset))
    pointer(code, 11, 0x80550000)
    if index < 16:
        for offset in range(0, 160, 4):
            pointer(code, 0, ((index + 1) * 0x1020304 + offset * 0x01010101) & 0xffffffff)
            code.append(dform(36, 0, 11, offset))
    pointer(code, 0, 0x12345678)
    code.append(spr(0, 9, True))
    pointer(code, 5, 0xaabbccdd)
    pointer(code, 3, address)
    pointer(code, 4, length)
    call = base + len(code) * 4
    code.append(branch(call, 0x80213060, True))
    for register, slot in [(3, 24), (4, 28), (5, 32), (1, 40), (2, 44), (13, 48), (30, 52), (31, 56)]:
        code.append(dform(36, register, 30, slot))
    code.extend([spr(0, 9, False), dform(36, 0, 30, 36), spr(0, 8, False), dform(36, 0, 30, 60),
        0x7c0000a6, dform(36, 0, 30, 64), spr(0, 1008, False), dform(36, 0, 30, 68)])
    for address_snapshot, slot in [(0x80550000, 128), (0xc0550000, 288)]:
        pointer(code, 11, address_snapshot)
        for offset in range(0, 160, 4):
            code.extend([dform(32, 0, 11, offset), dform(36, 0, 30, slot + offset)])
    pointer(code, 3, address)
    pointer(code, 4, length)
    code.append(branch(base + len(code) * 4, 0x80212fd0, True))
    pointer(code, 11, 0xc0550000)
    for offset in range(0, 160, 4):
        code.extend([dform(32, 0, 11, offset), dform(36, 0, 30, 448 + offset)])
    pointer(code, 0, 0xc001cafe)
    code.append(dform(36, 0, 30, 16))
    records.append({'index': index, 'address': address, 'length': length, 'warmCache': index < 16, 'call': call, 'return': call + 4})
halt = base + len(code) * 4
code.append(branch(halt, halt))
patches = []
exec(compile(source[source.index('while len(code) % 8:'):source.index('sha = lambda path:')], str(parent), 'exec'), globals())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'generation.json').write_text(json.dumps({'originalSha256': sha(original_path), 'harnessSha256': sha(output / 'fpr-init.dol'),
    'generatorSha256': sha(Path(__file__)), 'parentSha256': sha(parent), 'helperSha256': sha(helpers),
    'wrapperSha256': sha(experiment / 'run_dc_zero_dolphin.ps1'), 'baseRunnerSha256': sha(experiment / 'run_dolphin_probe.ps1'),
    'records': records, 'patches': [], 'limits': ['Unpatched original DCZeroRange/flush/vector installer, prepared cached pattern/rawA5/ABI/MSR2032/HID0C200.',
        'Dolphin accurate cache, no physical Wii cache timing or uncached/dcache-disabled dcbz acceptance.']}, indent=2) + '\n')
print('Generated32whole original DCZeroRange calls: populated and absent cache lines')

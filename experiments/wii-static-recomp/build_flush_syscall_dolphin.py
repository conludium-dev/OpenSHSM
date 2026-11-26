"""Measure whole original DCFlushRange and the original installed syscall vector."""
from pathlib import Path
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_si_query_dolphin.py'
source = parent.read_text()
prefix = source[:source.index('for index in range(16):')].replace('dolphin-si-query', 'dolphin-flush-syscall')
exec(compile(prefix, str(parent), 'exec'), globals())
code.extend([dform(14, 0, 0, 0x2032), (31 << 26) | (146 << 1)])
pointer(code, 0, 0xc200)
code.append(spr(0, 1008, True))
pointer(code, 1, 0x80540000)
pointer(code, 2, 0x805335e0)
pointer(code, 13, 0x8052e720)
code.append(branch(base + len(code) * 4, 0x8021a140, True))
for index in range(16):
    length = [0, 1, 31, 32, 33, 63, 64, 128][index % 8]
    misalignment = 0 if index < 8 else 7
    address = 0x80550000 + misalignment
    data[index * stride:index * stride + 16] = b'OSHSM_PPC_DLP001'
    struct.pack_into('>I', data, index * stride + 20, index)
    pointer(code, 30, 0xc0680000 + index * stride)
    pointer(code, 11, 0xc0550000)
    pointer(code, 0, 0xa5a5a5a5)
    for offset in range(0, 160, 4):
        code.append(dform(36, 0, 11, offset))
    pointer(code, 11, 0x80550000)
    for offset in range(0, 160, 32):
        pointer(code, 11, 0x80550000 + offset)
        code.append((31 << 26) | (11 << 11) | (470 << 1))
    pointer(code, 11, 0x80550000)
    for offset in range(0, 160, 4):
        pointer(code, 0, ((index + 1) * 0x1020304 + offset * 0x01010101) & 0xffffffff)
        code.append(dform(36, 0, 11, offset))
    pointer(code, 0, 0)
    code.extend([spr(0, 26, True), spr(0, 27, True)])
    pointer(code, 9, 0x11223344)
    pointer(code, 10, 0x55667788)
    pointer(code, 3, address)
    pointer(code, 4, length)
    call = base + len(code) * 4
    code.append(branch(call, 0x80212fd0, True))
    code.extend([0x7c0000a6, dform(36, 0, 30, 24), spr(0, 1008, False), dform(36, 0, 30, 28),
        spr(0, 26, False), dform(36, 0, 30, 32), spr(0, 27, False), dform(36, 0, 30, 36)])
    for register, slot in [(1, 40), (2, 44), (13, 48), (30, 52), (9, 56), (10, 60), (3, 64), (4, 68)]:
        code.append(dform(36, register, 30, slot))
    code.extend([spr(0, 8, False), dform(36, 0, 30, 72)])
    pointer(code, 11, 0xc0550000)
    for offset in range(0, 160, 4):
        code.extend([dform(32, 0, 11, offset), dform(36, 0, 30, 128 + offset)])
    pointer(code, 0, 0xc001cafe)
    code.append(dform(36, 0, 30, 16))
    records.append({'index': index, 'address': address, 'length': length, 'call': call, 'return': call + 4})
halt = base + len(code) * 4
code.append(branch(halt, halt))
patches = []
tail = source[source.index('while len(code) % 8:'):source.index('sha = lambda path:')]
exec(compile(tail, str(parent), 'exec'), globals())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'generation.json').write_text(json.dumps({'originalSha256': sha(original_path), 'harnessSha256': sha(output / 'fpr-init.dol'),
    'generatorSha256': sha(Path(__file__)), 'parentGeneratorSha256': sha(parent), 'helperSha256': sha(helpers),
    'baseRunnerSha256': sha(experiment / 'run_dolphin_probe.ps1'), 'wrapperSha256': sha(experiment / 'run_flush_syscall_dolphin.ps1'),
    'records': records, 'patches': patches, 'scope': 'Whole original syscall-vector installer then16DCFlushRange calls; CPU sc/rfi and physical cache visibility.',
    'limits': ['Prepared MSR2032/HID0C200/cache patterns/SP/r2-r13; Dolphin reference, not physical Wii timing/order or retail boot.',
        'Cached/uncached160bytes test data and dcbI setup; no original executable patches or direct syscall-handler call.']}, indent=2) + '\n')
print('Generated16original cache flush/syscall cases with original vector installer')

"""Whole original memory-protection initialization and repeated-call controls."""
from pathlib import Path
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_si_query_dolphin.py'
source = parent.read_text()
prefix = source[:source.index('for index in range(16):')].replace('dolphin-si-query', 'dolphin-memory-protection')
exec(compile(prefix, str(parent), 'exec'), globals())
bat_sprs = list(range(528, 544)) + list(range(560, 576))
def snapshot_bats(slot):
    for number, register in enumerate(bat_sprs):
        code.extend([spr(0, register, False), dform(36, 0, 30, slot + number * 4)])
for index in range(16):
    data[index * stride:index * stride + 16] = b'OSHSM_PPC_DLP001'
    struct.pack_into('>I', data, index * stride + 20, index)
    code.extend([dform(14, 0, 0, 0x2032), (31 << 26) | (146 << 1)])
    pointer(code, 0, 0xc200)
    code.append(spr(0, 1008, True))
    pointer(code, 1, 0x80540000)
    pointer(code, 2, 0x805335e0)
    pointer(code, 13, 0x8052e720)
    pointer(code, 30, 0xc0680000 + index * stride)
    pointer(code, 31, 0x55660000 + index)
    if index % 2 == 0:
        seeds = [(0x8052aae0, 0), (0x8052aad8, 0x80003040), (0x8052aaf8, 0), (0x8052aafc, 0),
            (0x800000c4, 0xfffffff0), (0x800000c8, 0), (0x80003100, 0x01800000), (0x80003104, 0x01800000),
            (0x8000311c, 0x04000000), (0x80003120, 0x93400000)]
        seeds += [(0x80003040 + offset, 0) for offset in range(0, 128, 4)]
        seeds += [(0x8042cfc8 + offset, 0) for offset in (8, 12)]
        for address, value in seeds:
            pointer(code, 11, address)
            pointer(code, 0, value)
            code.append(dform(36, 0, 11, 0))
    snapshot_bats(160)
    call = base + len(code) * 4
    code.append(branch(call, 0x80218680, True))
    code.extend([0x7c0000a6, dform(36, 0, 30, 24), spr(0, 1008, False), dform(36, 0, 30, 28)])
    for register, slot in [(1, 32), (2, 36), (13, 40), (30, 44), (31, 48)]:
        code.append(dform(36, register, 30, slot))
    code.extend([spr(0, 8, False), dform(36, 0, 30, 52), spr(0, 1011, False), dform(36, 0, 30, 56)])
    for number, address in enumerate([0x8052aae0, 0x800000c4, 0x800000c8, 0x8052aaf8, 0x8052aafc,
            0x8042cfd0, 0x8042cfd4] + [0x80003040 + i * 4 for i in range(5)]):
        pointer(code, 11, address)
        code.extend([dform(32, 0, 11, 0), dform(36, 0, 30, 60 + number * 4)])
    pointer(code, 11, 0xcc004000)
    for number, offset in enumerate((0x10, 0x1c, 0x20)):
        code.extend([dform(40, 0, 11, offset), dform(36, 0, 30, 108 + number * 4)])
    snapshot_bats(320)
    pointer(code, 0, 0xc001cafe)
    code.append(dform(36, 0, 30, 16))
    records.append({'index': index, 'firstCall': index % 2 == 0, 'call': call, 'return': call + 4})
halt = base + len(code) * 4
code.append(branch(halt, halt))
patches = []
tail = source[source.index('while len(code) % 8:'):source.index('sha = lambda path:')]
exec(compile(tail, str(parent), 'exec'), globals())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'generation.json').write_text(json.dumps({'originalSha256': sha(original_path), 'harnessSha256': sha(output / 'fpr-init.dol'),
    'generatorSha256': sha(Path(__file__)), 'parentGeneratorSha256': sha(parent), 'helperSha256': sha(helpers),
    'baseRunnerSha256': sha(experiment / 'run_dolphin_probe.ps1'), 'wrapperSha256': sha(experiment / 'run_memory_protection_dolphin.ps1'),
    'records': records, 'patches': patches, 'batSprs': bat_sprs,
    'scope': 'Whole original __OSInitMemoryProtection,8first calls and8idempotent controls; original BATConfig/real-mode/rfi paths retained.',
    'limits': ['Prepared24MB MEM1/64MB MEM2 with93400000usable end, interrupt table/masks/empty shutdown queue/CPU ABI.',
        'No original code patches; emulator final BAT/MI/table/queue state, not physical protection faults or retail boot.']}, indent=2) + '\n')
print('Generated16whole original memory-protection calls, no executable patches')

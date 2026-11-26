"""Exercise original memcpy with CPU-delivered FPU unavailable and the original OS handler."""
from pathlib import Path
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_si_query_dolphin.py'
source = parent.read_text()
prefix = source[:source.index('for index in range(16):')].replace('dolphin-si-query', 'dolphin-fpu-lazy')
exec(compile(prefix, str(parent), 'exec'), globals())
vector_address = 0x80211ba0
section = next(i for i in range(7) if header[18 + i] <= vector_address < header[18 + i] + header[36 + i])
vector_words = list(struct.unpack_from('>38I', original, header[section] + vector_address - header[18 + section]))
assert vector_words[26] == 0x38600000
vector_words[26] = 0x38600007
code.extend([dform(14, 0, 0, 0x2032), (31 << 26) | (146 << 1)])
pointer(code, 11, 0xc0000800)
for index, word in enumerate(vector_words):
    pointer(code, 0, word)
    code.append(dform(36, 0, 11, index * 4))
code.append(0x7c0004ac)
for index in range(16):
    unavailable = index % 2 == 0
    data[index * stride:index * stride + 16] = b'OSHSM_PPC_DLP001'
    struct.pack_into('>I', data, index * stride + 20, index)
    pointer(code, 0, 0xc200)
    code.append(spr(0, 1008, True))
    pointer(code, 1, 0x80540000)
    pointer(code, 2, 0x805335e0)
    pointer(code, 13, 0x8052e720)
    pointer(code, 30, 0xc0680000 + index * stride)
    pointer(code, 11, 0x80501000)
    pointer(code, 0, 0)
    for offset in range(0, 0x1c8, 4):
        code.append(dform(36, 0, 11, offset))
    for address, value in [(0x800000c0, 0x00501000), (0x800000d4, 0x80501000),
            (0x800000d8, 0), (0x8000301c, 0x80213dc0)]:
        pointer(code, 11, address)
        pointer(code, 0, value)
        code.append(dform(36, 0, 11, 0))
    for offset in range(0, 128, 4):
        word = ((index + 1) * 0x1020304 + offset * 0x01010101) & 0xffffffff
        pointer(code, 11, 0x80550000 + offset)
        pointer(code, 0, word)
        code.append(dform(36, 0, 11, 0))
        pointer(code, 11, 0x80560000 + offset)
        pointer(code, 0, 0xa5a5a5a5)
        code.append(dform(36, 0, 11, 0))
    code.extend([dform(14, 0, 0, 0x32 if unavailable else 0x2032), (31 << 26) | (146 << 1)])
    pointer(code, 3, 0x80560000)
    pointer(code, 4, 0x80550000)
    pointer(code, 5, 128)
    call = base + len(code) * 4
    code.append(branch(call, 0x80005f34, True))
    code.extend([0x7c0000a6, dform(36, 0, 30, 24)])
    for address, slot in [(0x800000d8, 28), (0x80501198, 32), (0x8050119c, 36)]:
        pointer(code, 11, address)
        code.extend([dform(32, 0, 11, 0), dform(36, 0, 30, slot)])
    pointer(code, 11, 0x805011a2)
    code.extend([dform(40, 0, 11, 0), dform(36, 0, 30, 40)])
    for register, slot in [(3, 44), (1, 48), (2, 52), (13, 56), (30, 60)]:
        code.append(dform(36, register, 30, slot))
    code.extend([spr(0, 8, False), dform(36, 0, 30, 64)])
    for address, result_offset in [(0x80560000, 128), (0x80550000, 256)]:
        pointer(code, 11, address)
        for offset in range(0, 128, 4):
            code.extend([dform(32, 0, 11, offset), dform(36, 0, 30, result_offset + offset)])
    pointer(code, 0, 0xc001cafe)
    code.append(dform(36, 0, 30, 16))
    records.append({'index': index, 'unavailable': unavailable, 'call': call, 'return': call + 4})
halt = base + len(code) * 4
code.append(branch(halt, halt))
patches = []
tail = source[source.index('while len(code) % 8:'):source.index('sha = lambda path:')]
exec(compile(tail, str(parent), 'exec'), globals())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'generation.json').write_text(json.dumps({'originalSha256': sha(original_path), 'harnessSha256': sha(output / 'fpr-init.dol'),
    'generatorSha256': sha(Path(__file__)), 'parentGeneratorSha256': sha(parent), 'helperSha256': sha(helpers),
    'baseRunnerSha256': sha(experiment / 'run_dolphin_probe.ps1'), 'wrapperSha256': sha(experiment / 'run_fpu_lazy_dolphin.ps1'),
    'records': records, 'vectorWords': vector_words, 'patches': patches,
    'scope': 'Original memcpy128bytes with real FPU exception800/ID7/original OSSwitchFPUContext/rfi or already-enabled control.',
    'limits': ['Prepared empty OSContext/owner0/vector/table/MSR/SP/r2-r13; no prior-owner save or populated FPU restoration proof.',
        'No original code patches; copied vector ID7 and fixture state are PC adaptations, not retail startup.']}, indent=2) + '\n')
print('Generated8original lazy-FPU copies and8FP-enabled controls')

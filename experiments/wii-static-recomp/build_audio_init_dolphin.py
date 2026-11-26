"""Run whole original OS audio startup with disclosed arena/IPL/cache fixtures."""
from pathlib import Path
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_si_query_dolphin.py'
source = parent.read_text()
prefix = source[:source.index('for index in range(16):')].replace('dolphin-si-query', 'dolphin-audio-init')
exec(compile(prefix, str(parent), 'exec'), globals())
code.extend([dform(14, 0, 0, 0x2032), (31 << 26) | (146 << 1)])
pointer(code, 0, 0xc200)
code.append(spr(0, 1008, True))
pointer(code, 1, 0x80540000)
pointer(code, 2, 0x805335e0)
pointer(code, 13, 0x8052e720)
code.append(branch(base + len(code) * 4, 0x8021a140, True))
for index in range(16):
    in_ipl = index % 2
    data[index * stride:index * stride + 16] = b'OSHSM_PPC_DLP001'
    struct.pack_into('>I', data, index * stride + 20, index)
    pointer(code, 1, 0x80540000)
    pointer(code, 2, 0x805335e0)
    pointer(code, 13, 0x8052e720)
    pointer(code, 30, 0xc0680000 + index * stride)
    pointer(code, 31, 0x55660000 + index)
    for address, value in [(0x8052aa98, 0x81700000), (0x8052aa38, in_ipl)]:
        pointer(code, 11, address)
        pointer(code, 0, value)
        code.append(dform(36, 0, 11, 0))
    pointer(code, 11, 0x81000000)
    for offset in range(0, 128, 4):
        pointer(code, 0, ((index + 1) * 0x1020304 + offset * 0x01010101) & 0xffffffff)
        code.append(dform(36, 0, 11, offset))
    pointer(code, 3, 0)
    call = base + len(code) * 4
    code.append(branch(call, 0x80212ce0, True))
    code.extend([0x7c0000a6, dform(36, 0, 30, 24), spr(0, 1008, False), dform(36, 0, 30, 28)])
    for register, slot in [(1, 32), (2, 36), (13, 40), (30, 44), (31, 48)]:
        code.append(dform(36, register, 30, slot))
    code.extend([spr(0, 8, False), dform(36, 0, 30, 52)])
    pointer(code, 11, 0xcc005000)
    for register, slot in [(0x12, 56), (0xa, 60), (0x4, 64), (0x6, 68), (0x20, 72), (0x22, 76), (0x24, 80), (0x26, 84), (0x28, 88), (0x2a, 92)]:
        code.extend([dform(40, 0, 11, register), dform(36, 0, 30, slot)])
    pointer(code, 11, 0x800000f8)
    code.extend([dform(32, 0, 11, 0), dform(36, 0, 30, 96)])
    for address, slot, size in [(0x81000000, 128, 128), (0xc1000000, 256, 128),
            (0x816fff80, 384, 128), (0xd0000000, 512, 32)]:
        pointer(code, 11, address)
        for offset in range(0, size, 4):
            code.extend([dform(32, 0, 11, offset), dform(36, 0, 30, slot + offset)])
    pointer(code, 0, 0xc001cafe)
    code.append(dform(36, 0, 30, 16))
    records.append({'index': index, 'inIpl': in_ipl, 'arenaHi': 0x81700000, 'call': call, 'return': call + 4})
halt = base + len(code) * 4
code.append(branch(halt, halt))
patches = []
tail = source[source.index('while len(code) % 8:'):source.index('sha = lambda path:')]
exec(compile(tail, str(parent), 'exec'), globals())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'generation.json').write_text(json.dumps({'originalSha256': sha(original_path), 'harnessSha256': sha(output / 'fpr-init.dol'),
    'generatorSha256': sha(Path(__file__)), 'parentGeneratorSha256': sha(parent), 'helperSha256': sha(helpers),
    'baseRunnerSha256': sha(experiment / 'run_dolphin_probe.ps1'), 'wrapperSha256': sha(experiment / 'run_audio_init_dolphin.ps1'),
    'records': records, 'patches': patches, 'scope': 'Whole original __OSInitAudioSystem80212CE0 plus original syscall vector installer; DSP reset/DMA/mailbox waits intact.',
    'limits': ['Prepared arenaHi81700000/InIPL0-1/cache test buffer/MSR2032/HID0C200/SP/r2-r13; emulator DSP HLE reference, not physical Wii.',
        'No original instruction patch; final state/memory only, command chronology and intermediate DMA/mailbox state not observed.']}, indent=2) + '\n')
print('Generated16whole original audio startup calls, no executable patches')

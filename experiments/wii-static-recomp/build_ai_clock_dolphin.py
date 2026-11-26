"""Capture original audio-clock programming with real SDK tick waits."""
from pathlib import Path
import argparse
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_si_query_dolphin.py'
source = parent.read_text()
prefix = source[:source.index('for index in range(16):')]
prefix = prefix.replace('dolphin-si-query', 'dolphin-ai-clock')
exec(compile(prefix, str(parent), 'exec'), globals())
parser = argparse.ArgumentParser()
parser.add_argument('--unobserved', action='store_true')
args = parser.parse_args()
output = Path('work/private-game/static-recomp') / ('dolphin-ai-clock-unobserved' if args.unobserved else 'dolphin-ai-clock')
output.mkdir(exist_ok=True)
for index in range(16):
    mode = index % 2
    data[index * stride:index * stride + 16] = b'OSHSM_PPC_DLP001'
    struct.pack_into('>I', data, index * stride + 20, index)
    code.extend([dform(14, 0, 0, 0x32), (31 << 26) | (146 << 1)])
    pointer(code, 0, 0xc200)
    code.append(spr(0, 1008, True))
    pointer(code, 1, 0x80540000)
    pointer(code, 2, 0x805335e0)
    pointer(code, 13, 0x8052e720)
    pointer(code, 30, 0xc0680000 + index * stride)
    pointer(code, 11, 0xc06e0000)
    code.append(dform(36, 30, 11, 0))
    pointer(code, 11, 0xcd800000)
    for register, slot in [(0x180, 24), (0x1cc, 28), (0x1d0, 32)]:
        code.extend([dform(32, 0, 11, register), dform(36, 0, 30, slot)])
    pointer(code, 11, 0x80000000)
    code.extend([dform(32, 0, 11, 0xf8), dform(36, 0, 30, 36)])
    pointer(code, 3, mode)
    code.append(branch(base + len(code) * 4, 0x80212ac0, True))
    pointer(code, 11, 0xcd800000)
    for register, slot in [(0x180, 40), (0x1cc, 44), (0x1d0, 48)]:
        code.extend([dform(32, 0, 11, register), dform(36, 0, 30, slot)])
    code.extend([0x7c0000a6, dform(36, 0, 30, 52)])
    for register, slot in [(1, 56), (2, 60), (13, 64), (30, 68)]:
        code.append(dform(36, register, 30, slot))
    code.extend([spr(0, 268, False), dform(36, 0, 30, 76)])
    pointer(code, 0, 0xc001cafe)
    code.append(dform(36, 0, 30, 16))
    records.append({'index': index, 'mode': mode})
halt = base + len(code) * 4
code.append(branch(halt, halt))
patches = []
sites = [(0x80212af8, 0x90040180, 0x180), (0x80212b04, 0x900401d0, 0x1d0),
    (0x80212b6c, 0x900401cc, 0x1cc), (0x80212b94, 0x900301cc, 0x1cc),
    (0x80212be0, 0x900301d0, 0x1d0), (0x80212c30, 0x900301d0, 0x1d0), (0x80212c80, 0x900301d0, 0x1d0)]
for address, opcode, register in ([] if args.unobserved else sites):
    section = next(i for i in range(7) if header[18 + i] <= address < header[18 + i] + header[36 + i])
    offset = header[section] + address - header[18 + section]
    assert struct.unpack_from('>I', original, offset)[0] == opcode
    trampoline = base + len(code) * 4
    words = [opcode, dform(36, 11, 1, -8), dform(36, 12, 1, -4)]
    pointer(words, 11, 0xc06e0000)
    words.extend([dform(32, 11, 11, 0), dform(32, 12, 11, 72), dform(14, 12, 12, 1), dform(36, 12, 11, 72), dform(14, 12, 12, -1)])
    words.extend([(21 << 26) | (12 << 21) | (12 << 16) | (5 << 11) | (26 << 1),
        (31 << 26) | (11 << 21) | (11 << 16) | (12 << 11) | (266 << 1), dform(36, 0, 11, 128)])
    pointer(words, 12, 0xcd800000)
    words.extend([dform(32, 12, 12, register), dform(36, 12, 11, 132), spr(12, 268, False), dform(36, 12, 11, 136)])
    pointer(words, 12, address)
    words.append(dform(36, 12, 11, 140))
    words.extend([dform(32, 11, 1, -8), dform(32, 12, 1, -4)])
    words.append(branch(trampoline + len(words) * 4, address + 4))
    code.extend(words)
    patches.append({'address': address, 'offset': offset, 'opcode': opcode, 'trampoline': trampoline, 'words': words})
tail = source[source.index('while len(code) % 8:'):]
tail = tail[:tail.index('sha = lambda path:')]
exec(compile(tail, str(parent), 'exec'), globals())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'generation.json').write_text(json.dumps({'originalSha256': sha(original_path), 'harnessSha256': sha(output / 'fpr-init.dol'),
    'generatorSha256': sha(Path(__file__)), 'parentGeneratorSha256': sha(parent), 'helperSha256': sha(helpers),
    'baseRunnerSha256': sha(experiment / 'run_dolphin_probe.ps1'), 'wrapperSha256': sha(experiment / 'run_ai_clock_dolphin.ps1'),
    'records': records, 'patches': patches, 'observed': not args.unobserved,
    'scope': 'Whole original __AIClockInit80212AC0 modes0/1, hardware registers unseeded and original OSGetTick wait loops intact.',
    'limits': ['Prepared MSR32/HID0C200/SP/r2-r13 and isolated Dolphin profile; hardware clock accuracy/physical Wii not established.',
        'Seven store observers replay originals and preserve r11/r12/CR/LR; mftb/store timings belong to the observed fixture.']}, indent=2) + '\n')
print('Generated16 original audio-clock calls, SDK tick waits retained')

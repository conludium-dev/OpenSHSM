"""Capture whole original SRAM initialization and its command/DMA phases."""
from pathlib import Path
import ast
import argparse
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
parser = argparse.ArgumentParser()
parser.add_argument('--unobserved', action='store_true')
args = parser.parse_args()
output = Path('work/private-game/static-recomp') / ('dolphin-sram-unobserved' if args.unobserved else 'dolphin-sram')
output.mkdir(exist_ok=True)
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
original = original_path.read_bytes()
assert hashlib.sha1(original).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = list(struct.unpack('>64I', original[:256]))
helpers = experiment / 'build_dolphin_probe.py'
namespace = {}
for node in ast.parse(helpers.read_text()).body:
    if isinstance(node, ast.FunctionDef):
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(helpers), 'exec'), namespace)
dform, spr, pointer, branch = (namespace[name] for name in ('dform', 'spr', 'pointer', 'branch'))
base, stride = 0x80600000, 736
code, records, data = [], [], bytearray(16 * stride)
for index in range(16):
    data[index * stride:index * stride + 16] = b'OSHSM_PPC_DLP001'
    struct.pack_into('>I', data, index * stride + 20, index)
    code.extend([dform(14, 0, 0, 0x2030), (31 << 26) | (146 << 1)])
    pointer(code, 0, 0xc200)
    code.append(spr(0, 1008, True))
    pointer(code, 0, 0xa0000000)
    code.append(spr(0, 920, True))
    pointer(code, 1, 0x80540000)
    pointer(code, 2, 0x805335e0)
    pointer(code, 13, 0x8052e720)
    pointer(code, 30, 0xc0680000 + index * stride)
    code.extend([dform(50, 31, 30, 704), (63 << 26) | (255 << 17) | (31 << 11) | (711 << 1)])
    if index >= 8:
        code.append(branch(base + len(code) * 4, 0x80210830, True))
    pointer(code, 11, 0xc06e0000)
    code.append(dform(36, 30, 11, 0))
    pointer(code, 11, 0x80491f50)
    pointer(code, 0, 0)
    for offset in range(0, 64, 4):
        code.append(dform(36, 0, 11, offset))
    pointer(code, 11, 0x80492600)
    pointer(code, 0, 0xa5a5a5a5)
    for offset in range(0, 80, 4):
        code.append(dform(36, 0, 11, offset))
    pointer(code, 11, 0xcd000000)
    pointer(code, 0, 0)
    code.append(dform(36, 0, 11, 0x6800))
    pointer(code, 0, 0x2000)
    code.append(dform(36, 0, 11, 0x6800))
    for register, slot in [(0x6800, 32), (0x680c, 36), (0x6810, 40)]:
        code.extend([dform(32, 0, 11, register), dform(36, 0, 30, slot)])
    pointer(code, 11, 0xcc000000)
    code.extend([dform(32, 0, 11, 0x3000), dform(36, 0, 30, 44)])
    code.append(branch(base + len(code) * 4, 0x80219670, True))
    code.extend([dform(36, 3, 30, 24), 0x7c0000a6, dform(36, 0, 30, 28)])
    pointer(code, 11, 0xcd000000)
    for register, slot in [(0x6800, 48), (0x680c, 52), (0x6810, 56)]:
        code.extend([dform(32, 0, 11, register), dform(36, 0, 30, slot)])
    pointer(code, 11, 0xcc000000)
    code.extend([dform(32, 0, 11, 0x3000), dform(36, 0, 30, 60)])
    for address, length, slot in [(0x80492600, 80, 64), (0x80491f50, 64, 144)]:
        pointer(code, 11, address)
        for offset in range(0, length, 4):
            code.extend([dform(32, 0, 11, offset), dform(36, 0, 30, slot + offset)])
    for register, slot in [(1, 388), (2, 392), (13, 396), (30, 400)]:
        code.append(dform(36, register, 30, slot))
    code.extend([(63 << 26) | (583 << 1), dform(54, 0, 30, 704)])
    pointer(code, 0, 0xc001cafe)
    code.append(dform(36, 0, 30, 16))
    records.append({'index': index, 'ni': index // 8, 'channel': 0, 'device': 1, 'clock': 3})
halt = base + len(code) * 4
code.append(branch(halt, halt))
patches = []
sites = [(0x8020da84, 0x90036810, 0, 208), (0x8020dac4, 0x9083680c, 4, 212),
    (0x8020dc60, 0x90836804, 4, 224), (0x8020dc64, 0x93836808, 28, 232),
    (0x8020dc70, 0x9003680c, 0, 240), (0x80219758, 0x7c600034, 3, 256)]
for address, opcode, register, slot in ([] if args.unobserved else sites):
    section = next(i for i in range(7) if header[18 + i] <= address < header[18 + i] + header[36 + i])
    offset = header[section] + address - header[18 + section]
    assert struct.unpack_from('>I', original, offset)[0] == opcode
    trampoline = base + len(code) * 4
    words = [opcode, dform(36, 11, 1, -8), dform(36, 12, 1, -4)]
    pointer(words, 11, 0xc06e0000)
    words.extend([dform(32, 11, 11, 0), dform(36, register, 11, slot)])
    if slot in (212, 224, 232, 240):
        register_offset = {212: 0x680c, 224: 0x6804, 232: 0x6808, 240: 0x680c}[slot]
        pointer(words, 12, 0xcd000000)
        words.extend([dform(32, 12, 12, register_offset), dform(36, 12, 11, slot + 4)])
    if slot in (212, 240):
        pointer(words, 12, 0xcd000000)
        words.extend([dform(32, 12, 12, 0x6800), dform(36, 12, 11, 220 if slot == 212 else 248)])
    if slot == 240:
        pointer(words, 12, 0xcc000000)
        words.extend([dform(32, 12, 12, 0x3000), dform(36, 12, 11, 252)])
    if slot == 256:
        for source_address, destination in [(0xc0492600, 260), (0x80492600, 324)]:
            pointer(words, 12, source_address)
            for index in range(16):
                words.extend([dform(32, 12, 12, 0), dform(36, 12, 11, destination + index * 4)])
                pointer(words, 12, source_address + (index + 1) * 4)
    words.extend([dform(32, 11, 1, -8), dform(32, 12, 1, -4)])
    words.append(branch(trampoline + len(words) * 4, address + 4))
    code.extend(words)
    patches.append({'address': address, 'offset': offset, 'opcode': opcode, 'trampoline': trampoline, 'words': words, 'slot': slot})
while len(code) % 8:
    code.append(0x60000000)
image = bytearray(original)
used = set()
for text, address, content in [(True, base, struct.pack('>' + 'I' * len(code), *code)), (False, 0x80680000, data)]:
    slot = next(i for i in (range(7) if text else range(7, 18)) if not header[36 + i] and i not in used)
    used.add(slot)
    header[slot], header[18 + slot], header[36 + slot] = len(image), address, len(content)
    image.extend(content)
for patch in patches:
    struct.pack_into('>I', image, patch['offset'], branch(patch['address'], patch['trampoline']))
header[56] = base
image[:256] = struct.pack('>64I', *header)
(output / 'fpr-init.dol').write_bytes(image)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'generation.json').write_text(json.dumps({'originalSha256': sha(original_path), 'harnessSha256': sha(output / 'fpr-init.dol'),
    'generatorSha256': sha(Path(__file__)), 'helperSha256': sha(helpers), 'baseRunnerSha256': sha(experiment / 'run_dolphin_probe.ps1'),
    'wrapperSha256': sha(experiment / 'run_sram_dolphin.ps1'), 'records': records, 'patches': patches, 'observed': not args.unobserved,
    'scope': 'Whole original __OSInitSram19670, command20000100/64-byte DMA/cache invalidation/UnlockSram; six replaying observers.',
    'limits': ['Prepared ECB/SCB/MSR/HID/r2-r13 and laboratory Dolphin SRAM settings; not retail startup/physical Wii.',
        'Observed r3 is not a documented return value from void __OSInitSram. Timing/all-register behavior remains unverified.']}, indent=2) + '\n')
print('Generated16 whole original SRAM initialization calls; original DMA and cache operations retained')

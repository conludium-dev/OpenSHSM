"""Run original EXIGetID with disclosed fixtures and replaying observers."""
from pathlib import Path
import ast
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-exi-getid')
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
base, result_base, stride = 0x80600000, 0x680000, 736
data, code, records = bytearray(16 * stride), [], []
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
    pointer(code, 30, 0xc0000000 + result_base + index * stride)
    code.extend([dform(50, 31, 30, 48), (63 << 26) | (255 << 17) | (31 << 11) | (711 << 1)])
    if index >= 8:
        code.append(branch(base + len(code) * 4, 0x80210830, True))
    pointer(code, 11, 0xc06e0000)
    code.append(dform(36, 30, 11, 0))
    pointer(code, 11, 0x80491f50)
    code.append(dform(14, 0, 0, 0))
    for offset in range(0, 64, 4):
        code.append(dform(36, 0, 11, offset))
    pointer(code, 11, 0x8052aa08)
    code.append(dform(36, 0, 11, 0))
    pointer(code, 11, 0xcd000000)
    code.extend([dform(36, 0, 11, 0x6800), dform(14, 0, 0, 0x2000), dform(36, 0, 11, 0x6800)])
    for target, slot in [(0x6800, 32), (0x680c, 36), (0x6810, 40)]:
        code.extend([dform(32, 0, 11, target), dform(36, 0, 30, slot)])
    pointer(code, 11, 0xcc000000)
    code.extend([dform(32, 0, 11, 0x3000), dform(36, 0, 30, 56)])
    pointer(code, 5, 0x80500000)
    pointer(code, 0, 0xa5a5a5a5)
    code.append(dform(36, 0, 5, 0))
    pointer(code, 3, 0)
    pointer(code, 4, 2)
    code.append(branch(base + len(code) * 4, 0x8020ecd0, True))
    code.append(dform(36, 3, 30, 24))
    pointer(code, 11, 0x80500000)
    code.extend([dform(32, 0, 11, 0), dform(36, 0, 30, 28)])
    pointer(code, 11, 0xcd000000)
    for target, slot in [(0x6800, 64), (0x680c, 68), (0x6810, 72)]:
        code.extend([dform(32, 0, 11, target), dform(36, 0, 30, slot)])
    pointer(code, 11, 0x8052aa08)
    code.extend([dform(32, 0, 11, 0), dform(36, 0, 30, 76)])
    pointer(code, 11, 0x80491f50)
    for offset in range(0, 64, 4):
        code.extend([dform(32, 0, 11, offset), dform(36, 0, 30, 80 + offset)])
    pointer(code, 11, 0xcc000000)
    code.extend([dform(32, 0, 11, 0x3000), dform(36, 0, 30, 60),
                 (31 << 26) | (83 << 1), dform(36, 0, 30, 44),
                 (63 << 26) | (583 << 1), dform(54, 0, 30, 704)])
    pointer(code, 0, 0xc001cafe)
    code.append(dform(36, 0, 30, 16))
    records.append({'index': index, 'ni': index // 8, 'channel': 0, 'device': 2, 'destinationInitial': 0xa5a5a5a5})
halt = base + len(code) * 4
code.append(branch(halt, halt))
patches = []
for address, opcode, kind in [(0x8020da84, 0x90036810, 'command'), (0x8020dac4, 0x9083680c, 'control'), (0x8020dd30, 0x80036810, 'response')]:
    section = next(i for i in range(7) if header[18 + i] <= address < header[18 + i] + header[36 + i])
    offset = header[section] + address - header[18 + section]
    assert struct.unpack_from('>I', original, offset)[0] == opcode
    trampoline = base + len(code) * 4
    code.extend([opcode, dform(36, 11, 1, -8), dform(36, 12, 1, -4)])
    pointer(code, 11, 0xc06e0000)
    code.append(dform(32, 11, 11, 0))
    if kind == 'control':
        code.extend([dform(32, 12, 11, 152), dform(14, 12, 12, 1), dform(36, 12, 11, 152), dform(14, 12, 12, -1)])
        code.append((21 << 26) | (12 << 21) | (12 << 16) | (5 << 11) | (26 << 1))
        code.append((31 << 26) | (11 << 21) | (11 << 16) | (12 << 11) | (266 << 1))
        code.append(dform(36, 4, 11, 160))
        for register, slot in [(0x680c, 164), (0x6800, 168), (0x6810, 172)]:
            pointer(code, 12, 0xcd000000)
            code.extend([dform(32, 12, 12, register), dform(36, 12, 11, slot)])
    else:
        code.append(dform(36, 0, 11, 144 if kind == 'command' else 148))
    code.extend([dform(32, 11, 1, -8), dform(32, 12, 1, -4)])
    code.append(branch(base + len(code) * 4, address + 4))
    patches.append({'address': address, 'offset': offset, 'opcode': opcode, 'trampoline': trampoline, 'kind': kind})
while len(code) % 8:
    code.append(0x60000000)
image = bytearray(original)
used = set()
for text, address, content in [(True, base, struct.pack('>' + 'I' * len(code), *code)), (False, 0x80000000 + result_base, data)]:
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
report = {'originalSha256': sha(original_path), 'harnessSha256': hashlib.sha256(image).hexdigest(),
          'generatorSha256': sha(Path(__file__)), 'helperSha256': sha(helpers), 'records': records, 'patches': patches,
          'baseRunnerSha256': sha(experiment / 'run_dolphin_probe.ps1'), 'wrapperSha256': sha(experiment / 'run_exi_getid_dolphin.ps1'),
          'scope': 'Whole original EXIGetID0/2 with replayed three displaced instructions; observers preserve r11/r12/CR/LR.',
          'limits': ['Synthetic MSR/HID0/GPR/zero ECB/cache/post-init CSR fixture, repeated16calls; not retail startup or physical Wii.',
                     'Observers add MMIO reads and scratch stack stores; emulator completion timing only.',
                     'Serial port1 forced None; response describes that configuration, not an attached device.']}
(output / 'generation.json').write_text(json.dumps(report, indent=2) + '\n')
print('Generated16 whole EXIGetID calls with3replaying observers')

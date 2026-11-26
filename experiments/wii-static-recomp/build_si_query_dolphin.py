"""Measure original SI status-query setup and completion on disconnected ports."""
from pathlib import Path
import ast
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-si-query')
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
    channel = index % 4
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
    pointer(code, 11, 0xc06e0000)
    code.append(dform(36, 30, 11, 0))
    pointer(code, 11, 0x8042b6f0)
    pointer(code, 0, 0xffffffff)
    code.append(dform(36, 0, 11, 0))
    pointer(code, 0, 0)
    for offset in (4, 8, 12, 16):
        code.append(dform(36, 0, 11, offset))
    pointer(code, 11, 0x8042b708 + channel * 4)
    pointer(code, 0, 0x80)
    code.append(dform(36, 0, 11, 0))
    pointer(code, 4, 0x80500000)
    pointer(code, 0, 0)
    code.append(dform(36, 0, 4, 0))
    pointer(code, 6, 0x80500010)
    pointer(code, 0, 0xa5a5a5a5)
    code.append(dform(36, 0, 6, 0))
    pointer(code, 11, 0xcc000000)
    code.extend([dform(32, 0, 11, 0x3000), dform(36, 0, 30, 76)])
    pointer(code, 3, channel)
    pointer(code, 5, 1)
    pointer(code, 7, 3)
    pointer(code, 8, 0)
    code.append(branch(base + len(code) * 4, 0x8020fd00, True))
    code.append(dform(36, 3, 30, 24))
    pointer(code, 11, 0xcd000000)
    for address, slot in [(0x6434, 28), (0x6438, 32), (0x6480, 36)]:
        code.extend([dform(32, 0, 11, address), dform(36, 0, 30, slot)])
    wait = base + len(code) * 4
    code.extend([dform(32, 0, 11, 0x6434), 0x540007ff])
    code.append(0x40820000 | ((wait - (base + len(code) * 4)) & 0xfffc))
    for address, slot in [(0x6434, 40), (0x6438, 44)]:
        code.extend([dform(32, 0, 11, address), dform(36, 0, 30, slot)])
    pointer(code, 11, 0x8042b6f0)
    code.extend([dform(32, 0, 11, 0), dform(36, 0, 30, 68)])
    pointer(code, 11, 0xcc000000)
    code.extend([dform(32, 0, 11, 0x3000), dform(36, 0, 30, 80)])
    code.append(branch(base + len(code) * 4, 0x8020f550, True))
    code.append(dform(36, 3, 30, 48))
    pointer(code, 11, 0x8042b708 + channel * 4)
    code.extend([dform(32, 0, 11, 0), dform(36, 0, 30, 52)])
    pointer(code, 11, 0x80500010)
    code.extend([dform(32, 0, 11, 0), dform(36, 0, 30, 56)])
    pointer(code, 11, 0xcd000000)
    for address, slot in [(0x6434, 60), (0x6438, 64)]:
        code.extend([dform(32, 0, 11, address), dform(36, 0, 30, slot)])
    pointer(code, 11, 0x8042b6f0)
    code.extend([dform(32, 0, 11, 0), dform(36, 0, 30, 72)])
    pointer(code, 0, 0xc001cafe)
    code.append(dform(36, 0, 30, 16))
    records.append({'index': index, 'channel': channel, 'requestBytes': 1, 'responseBytes': 3, 'callback': 0})
halt = base + len(code) * 4
code.append(branch(halt, halt))
patches = []
for address, opcode, slot in [(0x8020fe30, 0x90060080, 88), (0x8020fe8c, 0x90096434, 84)]:
    section = next(i for i in range(7) if header[18 + i] <= address < header[18 + i] + header[36 + i])
    offset = header[section] + address - header[18 + section]
    assert struct.unpack_from('>I', original, offset)[0] == opcode
    trampoline = base + len(code) * 4
    code.extend([dform(36, 11, 1, -8), dform(36, 12, 1, -4)])
    pointer(code, 11, 0xc06e0000)
    code.extend([dform(32, 11, 11, 0), dform(36, 0, 11, slot), dform(32, 11, 1, -8), dform(32, 12, 1, -4), opcode])
    code.append(branch(base + len(code) * 4, address + 4))
    patches.append({'address': address, 'offset': offset, 'opcode': opcode, 'trampoline': trampoline, 'slot': slot})
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
(output / 'generation.json').write_text(json.dumps({'originalSha256': sha(original_path), 'harnessSha256': sha(output / 'fpr-init.dol'),
    'generatorSha256': sha(Path(__file__)), 'helperSha256': sha(helpers), 'baseRunnerSha256': sha(experiment / 'run_dolphin_probe.ps1'),
    'wrapperSha256': sha(experiment / 'run_si_query_dolphin.ps1'), 'records': records, 'patches': patches,
    'scope': 'Whole original transfer-start8020FD00 and completion8020F550; fixture waits hardware START then invokes original completion explicitly.',
    'limits': ['Prepared Si owner/type/buffers/r2-r13/MSR/HID; not whole SIGetType/SITransfer/interrupt handler/callback route.',
        'SIDevice0..3=None; no attached controller, Wiimote, physical Wii or retail game image. Observers preserve r11/r12/CR/LR and replay stores.']}, indent=2) + '\n')
print('Generated16 original SI status-query packets:4ports×4repetitions, whole setup and completion')

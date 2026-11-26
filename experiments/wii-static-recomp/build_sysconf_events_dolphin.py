"""Add replaying, state-preserving observations to the verified whole-SC harness."""
from pathlib import Path
import ast
import hashlib
import json
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
subprocess.run(['python3', str(experiment / 'verify_sysconf_chain.py')], check=True)
base = root / 'dolphin-sysconf-long'
output = root / 'dolphin-sysconf-events-fixed'
output.mkdir(exist_ok=True)
image = bytearray((base / 'fpr-init.dol').read_bytes())
layout = list(struct.unpack('>64I', image[:256]))
helpers = experiment / 'build_dolphin_probe.py'
namespace = {}
for node in ast.parse(helpers.read_text()).body:
    if isinstance(node, ast.FunctionDef):
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(helpers), 'exec'), namespace)
dform, pointer, branch = (namespace[name] for name in ('dform', 'pointer', 'branch'))
text_address, data_address, stride, capacity = 0x806c0000, 0x806e0000, 1280, 256
code, patches = [], []
sites = [(1, 0x80242530, 0x39610030, 'IOS_OpenAsync_return'),
    (2, 0x80240680, 0x9421fff0, 'ISFS_callback_entry'),
    (3, 0x80244e30, 0x9421fff0, 'NAND_open_callback_entry'),
    (4, 0x80247730, 0x9421fff0, 'SC_open_callback_entry'),
    (5, 0x80247800, 0x9421fff0, 'SC_read_callback_entry'),
    (6, 0x802407d0, 0x2c1f0000, 'ISFS_after_higher_callback'),
    (7, 0x80241e9c, 0x806da454, 'IPC_before_packet_free'),
    (8, 0x802438b0, 0x9421ffe0, 'iosFree_entry'),
    (9, 0x80241c30, 0x5460103a, 'IPCWriteReg_entry')]
for kind, address, opcode, name in sites:
    section = next(i for i in range(7) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
    offset = layout[section] + address - layout[18 + section]
    assert struct.unpack_from('>I', image, offset)[0] == opcode
    start = text_address + len(code) * 4
    code.extend([dform(36, 0, 1, -32), dform(36, 11, 1, -28), dform(36, 12, 1, -24),
        0x7c000026, dform(36, 0, 1, -20), 0x7c0000a6, dform(36, 0, 1, -16)])
    code.extend([(21 << 26) | (11 << 16) | (17 << 6) | (15 << 1), (31 << 26) | (11 << 21) | (146 << 1)])
    pointer(code, 11, data_address | 0x40000000)
    code.extend([dform(32, 12, 11, 16), (10 << 26) | (12 << 16) | capacity])
    full_branch = len(code)
    code.append(0)
    code.extend([dform(14, 12, 12, 1), dform(36, 12, 11, 16), dform(14, 12, 12, -1)])
    code.extend([(21 << 26) | (12 << 21) | (10 << 11) | (21 << 1),
        (21 << 26) | (12 << 21) | (12 << 16) | (8 << 11) | (23 << 1),
        (31 << 26) | (12 << 21) | (12 << 11) | (266 << 1),
        (31 << 26) | (11 << 21) | (11 << 16) | (12 << 11) | (266 << 1),
        dform(14, 11, 11, 64)])
    pointer(code, 0, kind)
    code.append(dform(36, 0, 11, 0))
    pointer(code, 0, address)
    code.extend([dform(36, 0, 11, 4), dform(36, 1, 11, 8), 0x7c0802a6, dform(36, 0, 11, 12),
        dform(32, 0, 1, -16), dform(36, 0, 11, 16), dform(32, 0, 1, -20), dform(36, 0, 11, 20),
        dform(36, 3, 11, 24), dform(36, 4, 11, 28), dform(36, 31, 11, 32)])
    for slot, source in [(36, 0x804b2b4c), (40, 0x8052afbc), (44, 0x8052afa8),
        (48, 0x8052b008), (52, 0x804b2a80), (56, 0x804b2a84)]:
        pointer(code, 12, source)
        code.extend([dform(32, 0, 12, 0), dform(36, 0, 11, slot)])
    for slot, source, size in [(64, 0x935e0080, 64), (128, 0xd35e0080, 64),
        (192, 0x935e00e0, 64), (256, 0xd35e00e0, 64), (320, 0x935e1020, 320),
        (640, 0x804b3000, 400), (1040, 0x935e1000, 64), (1104, 0x935e0000, 64)]:
        pointer(code, 12, source)
        for index in range(0, size, 4):
            code.extend([dform(32, 0, 12, index), dform(36, 0, 11, slot + index)])
    done_branch = len(code)
    code.append(0)
    full = text_address + len(code) * 4
    code.extend([dform(14, 12, 0, 1), dform(36, 12, 11, 20)])
    restore = text_address + len(code) * 4
    code[full_branch] = (16 << 26) | (4 << 21) | (0 << 16) | ((full - (text_address + full_branch * 4)) & 0xfffc)
    code[done_branch] = branch(text_address + done_branch * 4, restore)
    code.extend([dform(32, 0, 1, -20), (31 << 26) | (255 << 12) | (144 << 1),
        dform(32, 11, 1, -28), dform(32, 12, 1, -24), dform(32, 0, 1, -16),
        (31 << 26) | (146 << 1), dform(32, 0, 1, -32), opcode])
    code.append(branch(text_address + len(code) * 4, address + 4))
    patches.append({'kind': kind, 'name': name, 'address': address, 'opcode': opcode, 'offset': offset,
        'trampoline': start, 'end': text_address + len(code) * 4, 'restore': restore})
while len(code) % 8:
    code.append(0x60000000)
events = bytearray(64 + stride * capacity)
events[:16] = b'OSHSM_SC_EVENTS1'
for text, address, data in [(True, text_address, struct.pack('>' + 'I' * len(code), *code)), (False, data_address, events)]:
    slot = next(i for i in (range(7) if text else range(7, 18)) if not layout[36 + i])
    layout[slot], layout[18 + slot], layout[36 + slot] = len(image), address, len(data)
    image.extend(data)
for patch in patches:
    struct.pack_into('>I', image, patch['offset'], branch(patch['address'], patch['trampoline']))
image[:256] = struct.pack('>64I', *layout)
(output / 'fpr-init.dol').write_bytes(image)
report = json.loads((base / 'generation.json').read_text())
report.update(generatorSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    harnessSha256=hashlib.sha256(image).hexdigest(), patches=patches,
    wrapperSha256=hashlib.sha256((experiment / 'run_sysconf_events_fixed_disc_dolphin.ps1').read_bytes()).hexdigest(),
    controlGenerationSha256=hashlib.sha256((base / 'generation.json').read_bytes()).hexdigest(),
    eventStride=stride, eventCapacity=capacity, eventAddress=data_address)
report['limits'] += ['Nine private replaying observers save/restore r0/r11/r12/CR/MSR, do not change LR/CTR/XER/FPR; original displaced word replayed.',
    'EE disabled during observer snapshots and restored; reads/scratch stack/timing perturbations disclosed. Endpoint comparison with unobserved control required.']
(output / 'generation.json').write_text(json.dumps(report, indent=2) + '\n')
print('Prepared original whole-SC observer fixture, nine replay sites, private event capacity256')

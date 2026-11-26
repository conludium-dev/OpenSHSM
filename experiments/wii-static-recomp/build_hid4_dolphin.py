"""Observe original HID4 setter plus an independently distinguishable BAT alias."""
from pathlib import Path
import ast
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-hid4-probe')
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
dform, spr, pointer, branch, capture = (namespace[name] for name in ('dform', 'spr', 'pointer', 'branch', 'capture'))
base, result_base, stride = 0x80600000, 0x680000, 736
values = [0x80000000, 0x82000000, 0x83900000, 0x81900000] * 2
data, code, records = bytearray(8 * stride), [], []
for index, value in enumerate(values):
    data[index * stride:index * stride + 16] = b'OSHSM_PPC_DLP001'
    struct.pack_into('>I', data, index * stride + 20, index)
    code.extend([dform(14, 0, 0, 0x2030), (31 << 26) | (146 << 1)])
    for ident, seed in [(1008, 0), (1011, 0x80000000), (920, 0xa0000000),
                        (568, 0), (570, 0), (572, 0), (574, 0),
                        (542, 0), (543, 0x00700022), (542, 0xa0000002),
                        (569, 0x00720022), (568, 0xa0000002)]:
        pointer(code, 0, seed)
        code.append(spr(0, ident, True))
    for location, contents in [(0xc0700000, 0x11223344), (0xc0720000, 0x55667788)]:
        pointer(code, 4, location)
        pointer(code, 0, contents)
        code.append(dform(36, 0, 4, 0))
    initial = [0x12340000 + register * 0x100 + index for register in range(32)]
    initial[1], initial[3] = 0x80540000, value
    for register in range(32):
        pointer(code, register, initial[register])
    cr, xer, ctr = 0x55555555, (0xa0000000 if index >= 4 else 0x20000000), 0x12340000 + index
    pointer(code, 0, cr)
    code.append((31 << 26) | (255 << 12) | (144 << 1))
    pointer(code, 0, ctr)
    code.append(spr(0, 9, True))
    pointer(code, 0, xer)
    code.append(spr(0, 1, True))
    call = base + len(code) * 4
    code.append(branch(call, 0x80210840, True))
    observer = []
    capture(observer, result_base + index * stride, uncached=True)
    completion = observer[-3:]
    code.extend(observer[:-3])
    code.extend([spr(11, 1011), dform(36, 11, 12, 712)])
    pointer(code, 11, 0xa0000000)
    code.extend([dform(32, 11, 11, 0), dform(36, 11, 12, 716)])
    for offset, ident in [(720, 542), (724, 543), (728, 568), (732, 569)]:
        code.extend([spr(11, ident), dform(36, 11, 12, offset)])
    code.extend(completion)
    records.append({'index': index, 'argument': value, 'initialGpr': initial, 'cr': cr, 'xer': xer,
                    'ctr': ctr, 'expectedLr': call + 4,
                    'expectedAlias': 0x55667788 if value & 0x02000000 else 0x11223344})
code.append(branch(base + len(code) * 4, base + len(code) * 4))
packed = struct.pack('>' + 'I' * len(code), *code)
image = bytearray(original)
for slot, address, content in [(next(i for i in range(7) if not header[36 + i]), base, packed),
                               (next(i for i in range(7, 18) if not header[36 + i]), 0x80000000 + result_base, data)]:
    header[slot], header[18 + slot], header[36 + slot] = len(image), address, len(content)
    image.extend(content)
header[56] = base
image[:256] = struct.pack('>64I', *header)
(output / 'fpr-init.dol').write_bytes(image)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = {'originalSha256': sha(original_path), 'harnessSha256': hashlib.sha256(image).hexdigest(),
          'generatorSha256': sha(Path(__file__)), 'helperSha256': sha(helpers), 'records': records,
          'baseRunnerSha256': sha(experiment / 'run_dolphin_probe.ps1'), 'wrapperSha256': sha(experiment / 'run_hid4_dolphin.ps1'),
          'resultPhysicalAddress': result_base,
          'scope': 'Original80-byte HID4 function unchanged; synthetic BAT3/BAT4 alias and EE=0, no physical or retail boot acceptance.'}
(output / 'generation.json').write_text(json.dumps(report, indent=2) + '\n')
print('Generated8private original HID4 calls plus BAT3/BAT4 competing alias samples; original game bytes unchanged')

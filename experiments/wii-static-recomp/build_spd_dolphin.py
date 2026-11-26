"""Observe original HID0 SPD setter function with unchanged Wii instructions."""
from pathlib import Path
import ast
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-spd-probe')
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
values = [0, 0x8000, 0xc000, 0xc200] * 2
data, code, records = bytearray(8 * stride), [], []
for index, prior in enumerate(values):
    data[index * stride:index * stride + 16] = b'OSHSM_PPC_DLP001'
    struct.pack_into('>I', data, index * stride + 20, index)
    code.extend([dform(14, 0, 0, 0x2030), (31 << 26) | (146 << 1)])
    for ident, value in [(1008, prior), (920, 0xa0000000)]:
        pointer(code, 0, value)
        code.append(spr(0, ident, True))
    initial = [0x12340000 + register * 0x100 + index for register in range(32)]
    initial[1] = 0x80540000
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
    code.append(branch(call, 0x80210800, True))
    capture(code, result_base + index * stride, uncached=True)
    records.append({'index': index, 'priorHid0': prior, 'initialGpr': initial, 'cr': cr, 'xer': xer,
                    'ctr': ctr, 'expectedLr': call + 4})
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
          'baseRunnerSha256': sha(experiment / 'run_dolphin_probe.ps1'), 'wrapperSha256': sha(experiment / 'run_spd_dolphin.ps1'),
          'scope': 'Original40-byte SPD function/getter/setter unchanged; synthetic register/cache/MSR setup, not speculative hardware timing or retail boot.'}
(output / 'generation.json').write_text(json.dumps(report, indent=2) + '\n')
print('Generated8private original SPD function cases; original game instructions unchanged')

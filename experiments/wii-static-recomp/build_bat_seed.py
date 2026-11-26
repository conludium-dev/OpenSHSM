"""Observe Dolphin DOL loader BAT/HID4 inputs without modifying game instructions."""
from pathlib import Path
import ast
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-bat-seed')
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
base, result_base, stride = 0x80600000, 0x680000, 864
registers = [1011, *range(528, 536), *range(560, 568), *range(536, 544), *range(568, 576)]
data, code = bytearray(8 * stride), []
for index in range(8):
    data[index * stride:index * stride + 16] = b'OSHSM_PPC_DLP001'
    struct.pack_into('>I', data, index * stride + 20, index)
    code.extend([dform(14, 0, 0, 0x2030), (31 << 26) | (146 << 1)])
    observer = []
    capture(observer, result_base + index * stride, uncached=True)
    code.extend(observer[:-3])
    for position, ident in enumerate(registers):
        code.extend([spr(11, ident), dform(36, 11, 12, 712 + position * 4)])
    code.extend(observer[-3:])
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
          'generatorSha256': sha(Path(__file__)), 'helperSha256': sha(helpers), 'registers': registers, 'stride': stride,
          'baseRunnerSha256': sha(experiment / 'run_dolphin_probe.ps1'), 'wrapperSha256': sha(experiment / 'run_bat_seed.ps1'),
          'scope': 'Dolphin DOL loader register inputs, eight repeated observations; not original game execution or physical Wii startup.'}
(output / 'generation.json').write_text(json.dumps(report, indent=2) + '\n')
print('Generated private BAT/HID4 loader observation; no original game instruction patches')

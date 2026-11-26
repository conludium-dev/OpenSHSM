"""Measure original OS time consumer and record its actual reader tick before adjustment."""
from pathlib import Path
import ast
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-os-time-probe')
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
values = [0, 1, 0xffffffff, 0x100000000, 0x7fffffffffffffff, 0x8000000000000000, 0xffffffff00000000, 0xffffffffffffffff]
adjustments = values * 8
data = bytearray(64 * stride)
code = []
records = []
for index, adjustment in enumerate(adjustments):
    data[index * stride:index * stride + 16] = b'OSHSM_PPC_DLP001'
    struct.pack_into('>I', data, index * stride + 20, index)
    code.extend([dform(14, 0, 0, 0x2030), (31 << 26) | (146 << 1)])
    pointer(code, 0, 0x4000)
    code.append(spr(0, 1008, True))
    pointer(code, 1, 0x80540000)
    for register in range(14, 32):
        pointer(code, register, 0x12340000 + register * 0x100)
    pointer(code, 4, 0xc00030d8)
    pointer(code, 0, adjustment >> 32)
    code.append(dform(36, 0, 4, 0))
    pointer(code, 0, adjustment & 0xffffffff)
    code.append(dform(36, 0, 4, 4))
    code.append((31 << 26) | (4 << 11) | (470 << 1))
    pointer(code, 0, 0x20000000)
    code.append(spr(0, 1, True))
    pointer(code, 11, 0xc0000000 + result_base + index * stride)
    call = base + len(code) * 4
    code.append(branch(call, 0x8021c030, True))
    records.append({'index': index, 'adjustment': adjustment, 'expectedLr': call + 4})
    capture(code, result_base + index * stride, uncached=True)
code.append(branch(base + len(code) * 4, base + len(code) * 4))
shim = base + len(code) * 4
code.extend([dform(36, 3, 11, 24), dform(36, 4, 11, 28), 0x4e800020])
packed = struct.pack('>' + 'I' * len(code), *code)
image = bytearray(original)
for slot, address, content in [(next(i for i in range(7) if not header[36 + i]), base, packed),
                                (next(i for i in range(7, 18) if not header[36 + i]), 0x80000000 + result_base, data)]:
    header[slot], header[18 + slot], header[36 + slot] = len(image), address, len(content)
    image.extend(content)
endpoint = 0x8021c014
slot = next(i for i in range(18) if header[18 + i] <= endpoint < header[18 + i] + header[36 + i])
offset = header[slot] + endpoint - header[18 + slot]
assert struct.unpack_from('>I', original, offset)[0] == 0x4e800020
struct.pack_into('>I', image, offset, branch(endpoint, shim))
header[56] = base
image[:256] = struct.pack('>64I', *header)
(output / 'fpr-init.dol').write_bytes(image)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = {'originalSha256': sha(original_path), 'harnessSha256': hashlib.sha256(image).hexdigest(),
          'generatorSha256': sha(Path(__file__)), 'helperSha256': sha(helpers), 'records': records,
          'baseRunnerSha256': sha(experiment / 'run_dolphin_probe.ps1'), 'wrapperSha256': sha(experiment / 'run_os_time_dolphin.ps1'),
          'readerReturnPatch': hex(endpoint), 'observer': hex(shim), 'resultPhysicalAddress': result_base,
          'scope': 'Original OS consumer and TB read instructions, disclosed return observer stores raw reader result; not retail startup/physical Wii.'}
(output / 'generation.json').write_text(json.dumps(report, indent=2) + '\n')
print('Generated64private original OS-time cases; return observer preserves registers/flags')

"""Observe original NI setter and an original-address frsp instruction at rounding boundaries."""
from pathlib import Path
import ast
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-ni-probe')
output.mkdir(exist_ok=True)
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
original = original_path.read_bytes()
assert hashlib.sha1(original).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = list(struct.unpack('>64I', original[:256]))
candidates = []
for section in range(7):
    for offset in range(0, header[36 + section] - 7, 4):
        opcode = struct.unpack_from('>I', original, header[section] + offset)[0]
        if opcode >> 26 == 63 and ((opcode >> 1) & 1023) == 12 and not opcode & 1:
            candidates.append((header[18 + section] + offset, opcode, header[section] + offset))
address, opcode, original_offset = candidates[0]
source, destination = (opcode >> 11) & 31, (opcode >> 21) & 31
scratch = next(index for index in range(32) if index not in (source, destination, 31))
helpers = experiment / 'build_dolphin_probe.py'
namespace = {}
for node in ast.parse(helpers.read_text()).body:
    if isinstance(node, ast.FunctionDef):
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(helpers), 'exec'), namespace)
dform, spr, pointer, branch, capture = (namespace[name] for name in ('dform', 'spr', 'pointer', 'branch', 'capture'))
base, result_base, constant_base, stride = 0x80600000, 0x680000, 0x80780000, 736
values = [0, 0x8000000000000000, 1, 0x0010000000000000, 0x36a0000000000000, 0xb6a0000000000000,
          0x3690000000000000, 0x380fffffc0000000, 0x380fffffffffffff, 0xb80fffffffffffff,
          0x3810000000000000, 0x3ff0000010000000, 0x3ff0000010000001,
          0x7ff0000000000000, 0xfff0000000000000, 0x7fefffffffffffff]
constants = b''.join(struct.pack('>Q', value) for value in values) + bytes(8)
constants += bytes((-len(constants)) % 32)
data, code, records, returns = bytearray(32 * stride), [], [], []
for index in range(32):
    if returns:
        replacement = []
        pointer(replacement, 10, base + len(code) * 4)
        code[returns[-1]:returns[-1] + 2] = replacement
    ni, value_index = index // 16, index % 16
    data[index * stride:index * stride + 16] = b'OSHSM_PPC_DLP001'
    struct.pack_into('>I', data, index * stride + 20, index)
    code.extend([dform(14, 0, 0, 0x2030), (31 << 26) | (146 << 1)])
    pointer(code, 0, 0)
    code.append(spr(0, 1008, True))
    pointer(code, 0, 0xa0000000)
    code.append(spr(0, 920, True))
    pointer(code, 4, constant_base + 16 * 8)
    code.extend([dform(50, 31, 4, 0), (63 << 26) | (255 << 17) | (31 << 11) | (711 << 1)])
    if ni:
        code.append(branch(base + len(code) * 4, 0x80210830, True))
    pointer(code, 4, constant_base + value_index * 8)
    code.append(dform(50, source, 4, 0))
    pointer(code, 9, 0xc0000000 + result_base + index * stride)
    code.extend([(63 << 26) | (scratch << 21) | (583 << 1), dform(54, scratch, 9, 24)])
    returns.append(len(code))
    pointer(code, 10, 0)
    code.append(branch(base + len(code) * 4, address, True))
    records.append({'index': index, 'ni': ni, 'inputBits': values[value_index]})
halt = base + len(code) * 4
replacement = []
pointer(replacement, 10, halt)
code[returns[-1]:returns[-1] + 2] = replacement
code.append(branch(halt, halt))
collector = base + len(code) * 4
observer = []
capture(observer, result_base, uncached=True)
observer[1:3] = [dform(24, 9, 12, 0), 0x60000000]
code.extend(observer)
code.extend([spr(10, 9, True), 0x4e800420])
while len(code) % 8:
    code.append(0x60000000)
packed = struct.pack('>' + 'I' * len(code), *code)
image = bytearray(original)
used = set()
for text, target, content in [(True, base, packed), (False, 0x80000000 + result_base, data), (False, constant_base, constants)]:
    slot = next(i for i in (range(7) if text else range(7, 18)) if not header[36 + i] and i not in used)
    used.add(slot)
    header[slot], header[18 + slot], header[36 + slot] = len(image), target, len(content)
    image.extend(content)
struct.pack_into('>I', image, original_offset + 4, branch(address + 4, collector))
header[56] = base
image[:256] = struct.pack('>64I', *header)
(output / 'fpr-init.dol').write_bytes(image)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = {'originalSha256': sha(original_path), 'harnessSha256': hashlib.sha256(image).hexdigest(),
          'generatorSha256': sha(Path(__file__)), 'helperSha256': sha(helpers), 'records': records,
          'baseRunnerSha256': sha(experiment / 'run_dolphin_probe.ps1'), 'wrapperSha256': sha(experiment / 'run_ni_dolphin.ps1'),
          'frspAddress': address, 'frspOpcode': opcode, 'frspSource': source, 'frspDestination': destination,
          'exitPatchOffset': original_offset + 4, 'exitPatchAddress': address + 4, 'collector': collector,
          'scope': 'Original NI setter and original-address frsp unchanged; adjacent exit observer branch, synthetic RN0 input fixtures; not full FP or retail boot.'}
(output / 'generation.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'Generated32NI/RN0 cases using original frsp {address:08X}:{opcode:08X}; exit patch only after instruction')

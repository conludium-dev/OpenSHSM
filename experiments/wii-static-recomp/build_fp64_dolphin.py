"""Observe original DOL double transfers with NI modes and raw IEEE bit patterns."""
from pathlib import Path
import ast
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-fp64')
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
base, result_base, constant_base, stride = 0x80600000, 0x680000, 0x80780000, 736
values = [0, 0x8000000000000000, 1, 0x8000000000000001, 0x000fffffffffffff, 0x0010000000000000,
          0x3ff0000000000000, 0xbff0000000000000, 0x7fefffffffffffff, 0xffefffffffffffff,
          0x7ff0000000000000, 0xfff0000000000000, 0x7ff8000000000001, 0xfff8000000000042,
          0x7ff0000000000001, 0xfff0000000000042]
constants = bytearray(16 * 32 + 32)
for index, value in enumerate(values):
    struct.pack_into('>Q', constants, index * 32, value)
    struct.pack_into('>Q', constants, index * 32 + 20, value)
struct.pack_into('>Q', constants, 16 * 32 + 8, 0x4008000000000000)
pairs = [(0x800060f4, 0x80006108), (0x80006100, 0x80006114),
         (0x801a2648, 0x800096d0), (0x801a40b0, 0x800096d0), (0x80005fa8, 0x801a4a6c)]

def word(address):
    section = next(index for index in range(7) if header[18 + index] <= address < header[18 + index] + header[36 + index])
    return struct.unpack_from('>I', original, header[section] + address - header[18 + section])[0]

def fields(opcode):
    return (opcode >> 21) & 31, (opcode >> 16) & 31, (opcode >> 11) & 31, ((opcode & 65535) ^ 32768) - 32768

data, code, records, returns = bytearray(320 * stride), [], [], []
for index in range(320):
    if returns:
        replacement = []
        pointer(replacement, 30, base + len(code) * 4)
        code[returns[-1]:returns[-1] + 2] = replacement
    pair = index // 64
    ni, alignment, value_index = (index % 64) // 32, (index % 32) // 16, index % 16
    load, store = pairs[pair]
    ld, st = word(load), word(store)
    fd, load_ra, load_rb, load_offset = fields(ld)
    fs, store_ra, store_rb, store_offset = fields(st)
    assert fd == fs and load_ra and store_ra
    data[index * stride:index * stride + 16] = b'OSHSM_PPC_DLP001'
    struct.pack_into('>I', data, index * stride + 20, index)
    code.extend([dform(14, 0, 0, 0x2030), (31 << 26) | (146 << 1)])
    pointer(code, 0, 0xc200)
    code.append(spr(0, 1008, True))
    pointer(code, 0, 0xa0000000)
    code.append(spr(0, 920, True))
    pointer(code, 1, 0x80540000)
    pointer(code, 29, 0xc0000000 + result_base + index * stride)
    pointer(code, 4, constant_base + 16 * 32)
    code.extend([dform(50, 31, 4, 0), (63 << 26) | (255 << 17) | (31 << 11) | (711 << 1),
                 dform(50, 31, 4, 8), (4 << 26) | (fd << 21) | (31 << 16) | (31 << 11) | (528 << 1)])
    if ni:
        code.append(branch(base + len(code) * 4, 0x80210830, True))
    input_address = constant_base + value_index * 32 + (20 if alignment else 0)
    pointer(code, load_ra, input_address - (0 if ld >> 26 == 31 else load_offset))
    if ld >> 26 == 31:
        pointer(code, load_rb, 0)
    destination = 0x80500000 + index * 16 + alignment * 4
    pointer(code, 27, destination)
    returns.append(len(code))
    pointer(code, 30, 0)
    code.append(branch(base + len(code) * 4, load, True))
    records.append({'index': index, 'ni': ni, 'bits': values[value_index], 'fd': fd, 'ps1': 0x4008000000000000,
                    'loadAddress': load, 'loadOpcode': ld, 'storeAddress': store, 'storeOpcode': st,
                    'inputAddress': input_address, 'destination': destination, 'loadRa': load_ra, 'storeRa': store_ra,
                    'initialLoadRa': input_address - (0 if ld >> 26 == 31 else load_offset),
                    'initialStoreRa': destination - (0 if st >> 26 == 31 else store_offset)})
halt = base + len(code) * 4
replacement = []
pointer(replacement, 30, halt)
code[returns[-1]:returns[-1] + 2] = replacement
code.append(branch(halt, halt))
patches = {}
for load, store in pairs:
    patches[load + 4] = base + len(code) * 4
    ld, st = word(load), word(store)
    _, load_ra, _, _ = fields(ld)
    _, store_ra, store_rb, store_offset = fields(st)
    code.append(dform(36, load_ra, 29, 712))
    if st >> 26 == 31:
        code.append(dform(24, 27, store_ra, 0))
        pointer(code, store_rb, 0)
    else:
        code.append(dform(14, store_ra, 27, -store_offset))
    code.append(branch(base + len(code) * 4, store, True))
collector = base + len(code) * 4
for _, store in pairs:
    patches[store + 4] = collector
observer = []
capture(observer, result_base, uncached=True)
observer[1:3] = [dform(24, 29, 12, 0), 0x60000000]
marker = observer[-3:]
code.extend(observer[:-3])
code.extend([dform(32, 11, 27, 0), dform(36, 11, 12, 24), dform(32, 11, 27, 4), dform(36, 11, 12, 28)])
code.extend(marker)
code.extend([spr(30, 9, True), 0x4e800420])
while len(code) % 8:
    code.append(0x60000000)
image = bytearray(original)
used = set()
for text, address, content in [(True, base, struct.pack('>' + 'I' * len(code), *code)),
                               (False, 0x80000000 + result_base, data), (False, constant_base, constants)]:
    slot = next(i for i in (range(7) if text else range(7, 18)) if not header[36 + i] and i not in used)
    used.add(slot)
    header[slot], header[18 + slot], header[36 + slot] = len(image), address, len(content)
    image.extend(content)
patch_records = []
for address, target in patches.items():
    section = next(index for index in range(7) if header[18 + index] <= address < header[18 + index] + header[36 + index])
    offset = header[section] + address - header[18 + section]
    struct.pack_into('>I', image, offset, branch(address, target))
    patch_records.append({'address': address, 'offset': offset})
header[56] = base
image[:256] = struct.pack('>64I', *header)
(output / 'fpr-init.dol').write_bytes(image)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = {'originalSha256': sha(original_path), 'harnessSha256': hashlib.sha256(image).hexdigest(),
          'generatorSha256': sha(Path(__file__)), 'helperSha256': sha(helpers), 'records': records,
          'baseRunnerSha256': sha(experiment / 'run_dolphin_probe.ps1'), 'wrapperSha256': sha(experiment / 'run_fp64_dolphin.ps1'),
          'patches': patch_records, 'scope': 'Original six double-transfer forms and NI setter unchanged; adjacent observer exits, synthetic register/cache/input fixtures.'}
(output / 'generation.json').write_text(json.dumps(report, indent=2) + '\n')
print('Generated320original double-transfer cases: six forms, NI0/NI1,4/8-byte alignment,16IEEE patterns')

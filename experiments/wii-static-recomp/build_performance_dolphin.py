"""Observe the original six-setter boot sequence without changing its instructions."""
from pathlib import Path
import ast
import hashlib
import json
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
subprocess.run(['python3', str(experiment / 'analyze_performance_init.py')], check=True)
output = Path('work/private-game/static-recomp/dolphin-performance-probe')
output.mkdir(exist_ok=True)
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
original = original_path.read_bytes()
header = list(struct.unpack('>64I', original[:256]))
helpers = experiment / 'build_dolphin_probe.py'
namespace = {}
for node in ast.parse(helpers.read_text()).body:
    if isinstance(node, ast.FunctionDef):
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(helpers), 'exec'), namespace)
dform, spr, pointer, branch, capture = (namespace[name] for name in ('dform', 'spr', 'pointer', 'branch', 'capture'))
base, result_base, stride = 0x80600000, 0x680000, 736
code, records, returns = [], [], []
values = [0, 1, 0x7fffffff, 0x80000000, 0xffffffff, 0x12345678, 0x55555555, 0xaaaaaaaa]
data = bytearray(len(values) * stride)
registers = [952, 956, 953, 954, 957, 958]
for index, value in enumerate(values):
    if returns:
        location = returns[-1]
        replacement = []
        pointer(replacement, 10, base + len(code) * 4)
        code[location:location + 2] = replacement
        records[-1]['initialGpr'][10] = base + len(code) * 4
    data[index * stride:index * stride + 16] = b'OSHSM_PPC_DLP001'
    struct.pack_into('>I', data, index * stride + 20, index)
    code.extend([dform(14, 0, 0, 0x2030), (31 << 26) | (146 << 1)])
    for ident, seed in [(1008, 0x4000), (920, 0xa0000000), (952, 0x80000000), (956, 0),
                        (953, value), (954, value ^ 0x12345678), (957, value ^ 0xaaaaaaaa), (958, value ^ 0xffffffff)]:
        pointer(code, 0, seed)
        code.append(spr(0, ident, True))
    initial = [0x12340000 + register * 0x100 + index for register in range(32)]
    initial[1] = 0x80540000
    initial[9] = 0xc0000000 + result_base + index * stride
    for register in range(32):
        pointer(code, register, initial[register])
    cr, xer, ctr = (0xaaaaaaaa if index & 1 else 0x55555555), (0xe000007f if index & 1 else 0x20000000), value
    pointer(code, 0, cr)
    code.append((31 << 26) | (255 << 12) | (144 << 1))
    pointer(code, 0, ctr)
    code.append(spr(0, 9, True))
    pointer(code, 0, xer)
    code.append(spr(0, 1, True))
    initial[0] = xer
    returns.append(len(code))
    pointer(code, 10, 0)
    code.append(branch(base + len(code) * 4, 0x802113a8))
    records.append({'index': index, 'initialPmcSeed': value, 'initialGpr': initial, 'cr': cr, 'xer': xer, 'ctr': ctr})
halt = base + len(code) * 4
replacement = []
pointer(replacement, 10, halt)
code[returns[-1]:returns[-1] + 2] = replacement
records[-1]['initialGpr'][10] = halt
code.append(branch(halt, halt))
collector = base + len(code) * 4
collector_code = []
capture(collector_code, result_base, uncached=True)
assert len(collector_code) > 3
completion = collector_code[-3:]
collector_code = collector_code[:-3]
collector_code[1:3] = [dform(24, 9, 12, 0), 0x60000000]
for index, ident in enumerate(registers):
    collector_code.extend([spr(11, ident), dform(36, 11, 12, 712 + index * 4)])
collector_code.extend(completion)
collector_code.extend([spr(10, 9, True), 0x4e800420])
code.extend(collector_code)
packed = struct.pack('>' + 'I' * len(code), *code)
image = bytearray(original)
for slot, address, content in [(next(i for i in range(7) if not header[36 + i]), base, packed),
                               (next(i for i in range(7, 18) if not header[36 + i]), 0x80000000 + result_base, data)]:
    header[slot], header[18 + slot], header[36 + slot] = len(image), address, len(content)
    image.extend(content)
endpoint = 0x802113d8
slot = next(i for i in range(18) if header[18 + i] <= endpoint < header[18 + i] + header[36 + i])
offset = header[slot] + endpoint - header[18 + slot]
assert struct.unpack_from('>I', original, offset)[0] == 0x3c608390
struct.pack_into('>I', image, offset, branch(endpoint, collector))
header[56] = base
image[:256] = struct.pack('>64I', *header)
(output / 'fpr-init.dol').write_bytes(image)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = {'originalSha256': sha(original_path), 'harnessSha256': hashlib.sha256(image).hexdigest(),
          'generatorSha256': sha(Path(__file__)), 'helperSha256': sha(helpers), 'records': records,
          'baseRunnerSha256': sha(experiment / 'run_dolphin_probe.ps1'),
          'wrapperSha256': sha(experiment / 'run_performance_dolphin.ps1'),
          'exitPatch': hex(endpoint), 'exitPatchOffset': offset, 'collector': hex(collector),
          'resultPhysicalAddress': result_base, 'registers': registers,
          'scope': 'Original zero-argument sequence and six setters unchanged; measurement exit branch after sequence. Synthetic frozen preload and EE=0; not physical counters/retail boot.'}
(output / 'generation.json').write_text(json.dumps(report, indent=2) + '\n')
print('Generated8private original six-register reset cases; exit patch only after original sequence')

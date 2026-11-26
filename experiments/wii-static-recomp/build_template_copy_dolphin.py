"""Execute original template store and original memcpy in disclosed synthetic fixtures."""
from pathlib import Path
import ast
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-template-copy')
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
store, target, template, length, memcpy = 0x802119a8, 0x80211c08, 0x80211ba0, 152, 0x80005f34
section = next(i for i in range(7) if header[18 + i] <= store < header[18 + i] + header[36 + i])
store_offset = header[section] + store - header[18 + section]
assert struct.unpack_from('>I', original, store_offset)[0] == 0x901c0000
data, code, records, returns = bytearray(16 * stride), [], [], []
for index in range(16):
    if returns:
        replacement = []
        pointer(replacement, 31, base + len(code) * 4)
        code[returns[-1]:returns[-1] + 2] = replacement
    data[index * stride:index * stride + 16] = b'OSHSM_PPC_DLP001'
    struct.pack_into('>I', data, index * stride + 20, index)
    code.extend([dform(14, 0, 0, 0x2030), (31 << 26) | (146 << 1)])
    pointer(code, 0, 0xc200)
    code.append(spr(0, 1008, True))
    pointer(code, 0, 0xa0000000)
    code.append(spr(0, 920, True))
    pointer(code, 1, 0x80540000)
    pointer(code, 30, 0xc0000000 + result_base + index * stride)
    pointer(code, 27, 0x80500000 + index * 256)
    pointer(code, 28, target)
    pointer(code, 0, 0x38600000 | index)
    returns.append(len(code))
    pointer(code, 31, 0)
    code.append(branch(base + len(code) * 4, store, True))
    records.append({'index': index, 'value': 0x38600000 | index, 'destination': 0x80500000 + index * 256})
halt = base + len(code) * 4
replacement = []
pointer(replacement, 31, halt)
code[returns[-1]:returns[-1] + 2] = replacement
code.append(branch(halt, halt))
observer = base + len(code) * 4
code.append(dform(36, 0, 30, 24))
code.append(dform(24, 27, 3, 0))
pointer(code, 4, template)
code.append(dform(14, 5, 0, length))
code.append(branch(base + len(code) * 4, memcpy, True))
code.append(dform(36, 3, 30, 28))
pointer(code, 4, target)
code.extend([dform(32, 0, 4, 0), dform(36, 0, 30, 32)])
for offset in range(0, length, 4):
    code.extend([dform(32, 0, 27, offset), dform(36, 0, 30, 192 + offset)])
pointer(code, 0, 0xc001cafe)
code.append(dform(36, 0, 30, 16))
code.extend([spr(31, 9, True), 0x4e800420])
while len(code) % 8:
    code.append(0x60000000)
packed = struct.pack('>' + 'I' * len(code), *code)
image = bytearray(original)
used = set()
for text, address, content in [(True, base, packed), (False, 0x80000000 + result_base, data)]:
    slot = next(i for i in (range(7) if text else range(7, 18)) if not header[36 + i] and i not in used)
    used.add(slot)
    header[slot], header[18 + slot], header[36 + slot] = len(image), address, len(content)
    image.extend(content)
struct.pack_into('>I', image, store_offset + 4, branch(store + 4, observer))
header[56] = base
image[:256] = struct.pack('>64I', *header)
(output / 'fpr-init.dol').write_bytes(image)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = {'originalSha256': sha(original_path), 'harnessSha256': hashlib.sha256(image).hexdigest(),
          'generatorSha256': sha(Path(__file__)), 'helperSha256': sha(helpers), 'records': records,
          'baseRunnerSha256': sha(experiment / 'run_dolphin_probe.ps1'),
          'wrapperSha256': sha(experiment / 'run_template_copy_dolphin.ps1'),
          'storeAddress': store, 'storeOpcode': 0x901c0000, 'storeTarget': target,
          'template': template, 'templateBytes': length, 'memcpy': memcpy,
          'exitPatchOffset': store_offset + 4, 'exitPatchAddress': store + 4,
          'scope': 'Original store and memcpy unchanged; synthetic HID0/MSR/register/ordinary RAM destination fixtures.',
          'limits': ['NI mode and full OS exception loop not executed; isolated store/copy behavior only.',
                     'Observer reads CPU-visible cached bytes; no physical Wii/cache timing or exception-vector dispatch proof.']}
(output / 'generation.json').write_text(json.dumps(report, indent=2) + '\n')
print('Generated16 original store/template-copy cases; one adjacent observer patch, no original store/memcpy edits')

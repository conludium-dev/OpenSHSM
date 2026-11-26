"""Reuse verified bootstrap fixture, observe CPU-visible state before unknown L2CR read."""
from pathlib import Path
import ast
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-dcache-probe')
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
original = original_path.read_bytes()
assert hashlib.sha1(original).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = list(struct.unpack('>64I', original[:256]))
fixture_path = Path('work/private-game/static-recomp/dolphin-probe/boot.dol')
fixture = fixture_path.read_bytes()
prior = struct.unpack('>64I', fixture[:256])
slot = next(index for index in range(7) if prior[18 + index] == 0x80600000)
fixture_code = list(struct.unpack('>' + 'I' * (prior[36 + slot] // 4), fixture[prior[slot]:prior[slot] + prior[36 + slot]]))
stop = next(index for index, opcode in enumerate(fixture_code) if opcode >> 26 == 18 and not (opcode & 3)
            and 0x80600000 + index * 4 + ((opcode & 0x03fffffc) - (0x04000000 if opcode & 0x02000000 else 0)) == 0x80006310)
code = fixture_code[:stop + 1]
collector = 0x80600000 + len(code) * 4
helpers = experiment / 'build_dolphin_probe.py'
tree = ast.parse(helpers.read_text())
namespace = {'RESULT': 0x2000}
for node in tree.body:
    if isinstance(node, ast.FunctionDef):
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(helpers), 'exec'), namespace)
namespace['capture'](code, 0x2000, uncached=True)
completion = code[-3:]
del code[-3:]
for index in range(16):
    code.append(namespace['dform'](32, 11, 1, -16 + index * 4))
    code.append(namespace['dform'](36, 11, 12, 736 + index * 4))
code += completion
code.append(namespace['branch'](0x80600000 + len(code) * 4, 0x80600000 + len(code) * 4))
packed = struct.pack('>' + 'I' * len(code), *code)
data = bytearray(800)
data[:16] = b'OSHSM_PPC_DLP001'
image = bytearray(original)
for index, address, content in [(next(i for i in range(7) if not header[36 + i]), 0x80600000, packed),
                                (next(i for i in range(7, 18) if not header[36 + i]), 0x80002000, data)]:
    header[index], header[18 + index], header[36 + index] = len(image), address, len(content)
    image.extend(content)
endpoint = 0x802106c0
index = next(i for i in range(18) if header[18 + i] <= endpoint < header[18 + i] + header[36 + i])
offset = header[index] + endpoint - header[18 + index]
opcode = struct.unpack_from('>I', original, offset)[0]
assert opcode >> 26 == 31 and ((opcode >> 1) & 1023) == 339
assert ((opcode >> 16) & 31) | (((opcode >> 11) & 31) << 5) == 1017
struct.pack_into('>I', image, offset, namespace['branch'](endpoint, collector))
header[56] = 0x80600000
image[:256] = struct.pack('>64I', *header)
(output / 'boot.dol').write_bytes(image)
report = {'originalSha256': sha(original_path), 'harnessSha256': hashlib.sha256(image).hexdigest(),
          'fixtureSha256': sha(fixture_path), 'helperSha256': sha(helpers), 'generatorSha256': sha(Path(__file__)),
          'wrapperSha256': sha(experiment / 'run_dcache_probe.ps1'), 'baseRunnerSha256': sha(experiment / 'run_dolphin_probe.ps1'),
          'endpoint': hex(endpoint), 'originalOpcode': hex(opcode), 'collector': hex(collector),
          'scope': 'Private measurement branch before L2CR read, original DCE untouched; CPU cached stack copied to uncached result.'}
(output / 'generation.json').write_text(json.dumps(report, indent=2) + '\n')
print('Generated accurate-cache boot endpoint before original L2CR read')

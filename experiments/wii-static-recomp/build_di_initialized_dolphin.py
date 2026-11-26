"""Replace the laboratory's manual packet-heap creation with original IPCCltInit."""
from pathlib import Path
import ast
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
source = root / 'dolphin-di-open'
output = root / 'dolphin-di-initialized'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
observation = root / 'mass-di-inputs-observer/observation.json'
report = json.loads(observation.read_text())
assert report['observations'].count('DI_IPC_INPUTS 935e0000 93600000 935e25e0 93600000 1 935e25c0 935e2540 ffffffff 1 1') == 1
for row in report['records']:
    assert sha(Path(row['source'])) == row['sourceSha256']
    assert sha(Path(row['object'])) == row['objectSha256']
assert len(report['records']) == 125
assert sha(observation.with_name('observation.log')) == report['logSha256']
helpers = experiment / 'build_dolphin_probe.py'
namespace = {}
for node in ast.parse(helpers.read_text()).body:
    if isinstance(node, ast.FunctionDef):
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(helpers), 'exec'), namespace)
dform, pointer, branch, spr = (namespace[name] for name in ('dform', 'pointer', 'branch', 'spr'))
image = bytearray((source / 'fpr-init.dol').read_bytes())
layout = list(struct.unpack('>64I', image[:256]))
main = next(i for i in range(7) if layout[18 + i] == 0x80600000)
words = struct.unpack_from('>' + 'I' * (layout[36 + main] // 4), image, layout[main])
matches = []
for index, word in enumerate(words):
    address = 0x80600000 + index * 4
    displacement = word & 0x03fffffc
    if displacement & 0x02000000:
        displacement -= 0x04000000
    if word >> 26 == 18 and word & 3 == 1 and address + displacement == 0x80243570:
        matches.append(index)
assert len(matches) == 1
index = matches[0]
site = 0x80600000 + index * 4
offset = layout[main] + index * 4
text = 0x806c0000
code = [dform(37, 1, 1, -16), spr(0, 8), dform(36, 0, 1, 20)]
for address, value in [(0x80528a38, 0x935e0000), (0x8052ab10, 0x93600000)]:
    pointer(code, 11, address)
    pointer(code, 0, value)
    code.append(dform(36, 0, 11, 0))
call = text + len(code) * 4
code.append(branch(call, 0x802420b0, True))
code.extend([dform(32, 0, 1, 20), spr(0, 8, True), dform(14, 1, 1, 16), 0x4e800020])
slot = next(i for i in range(7) if not layout[36 + i])
payload = struct.pack('>' + 'I' * len(code), *code)
layout[slot], layout[18 + slot], layout[36 + slot] = len(image), text, len(payload)
image.extend(payload)
struct.pack_into('>I', image, offset, branch(site, text, True))
image[:256] = struct.pack('>64I', *layout)
(output / 'fpr-init.dol').write_bytes(image)
generation = json.loads((source / 'generation.json').read_text())
generation.update({'generatorSha256': sha(Path(__file__)), 'helperSha256': sha(helpers),
    'parentHarnessSha256': sha(source / 'fpr-init.dol'), 'parentGenerationSha256': sha(source / 'generation.json'),
    'nativeInputsSha256': sha(observation), 'harnessSha256': hashlib.sha256(image).hexdigest(),
    'initializerReplacement': {'site': site, 'offset': offset, 'originalTarget': 0x80243570,
        'text': text, 'call': call, 'target': 0x802420b0, 'bytes': len(payload), 'slot': slot},
    'limits': ['Only initial synthetic heap-create call replaced; original IPCCltInit creates heap and initialization state before pending STM.',
        'OS IPC source bounds 935E0000..93600000 are measured native laboratory preconditions, not physical retail bootstrap.',
        'No forced success flags, descriptors, callbacks, DI results or disc data; repeated DVDLowInit opens again, not idempotent.']})
(output / 'generation.json').write_text(json.dumps(generation, indent=2) + '\n')
print('Prepared original IPCCltInit before pending STM, whole SC and two whole DVDLowInit calls')

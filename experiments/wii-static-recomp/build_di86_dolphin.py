"""Call original DI86 after whole SC/DI OPEN; re-enable lab IRQ only after API capture."""
from pathlib import Path
import ast
import hashlib
import json
import struct

root = Path('work/private-game/static-recomp')
source = root / 'dolphin-di-initialized'
output = root / 'dolphin-di86'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
inputs_path = root / 'mass-di86-inputs-observer/observation.json'
inputs = json.loads(inputs_path.read_text())
assert 'DI86_INPUTS 3 1 1 935e2540 935e25e0' in inputs['observations']
state_line = next(line for line in inputs['observations'] if line.startswith('DI86_CALLBACK_STATE '))
state = bytes(map(int, state_line.split()[1:]))
assert struct.unpack_from('>4I', state) == (0, 1, 0x01000000, 0xfeebdaed)
assert sha(inputs_path.with_name('observation.log')) == inputs['logSha256']
for row in inputs['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
helpers = Path('experiments/wii-static-recomp/build_dolphin_probe.py')
namespace = {}
for node in ast.parse(helpers.read_text()).body:
    if isinstance(node, ast.FunctionDef):
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(helpers), 'exec'), namespace)
dform, pointer, branch, spr = (namespace[name] for name in ('dform', 'pointer', 'branch', 'spr'))
image = bytearray((source / 'fpr-init.dol').read_bytes())
layout = list(struct.unpack('>64I', image[:256]))
main = next(i for i in range(7) if layout[18 + i] == 0x80600000)
words = struct.unpack_from('>' + 'I' * (layout[36 + main] // 4), image, layout[main])
calls = []
for index, word in enumerate(words):
    displacement = word & 0x03fffffc
    if displacement & 0x02000000:
        displacement -= 0x04000000
    if word >> 26 == 18 and word & 3 == 1 and 0x80600000 + index * 4 + displacement == 0x80225a70:
        calls.append(index)
assert len(calls) == 2
index = calls[1]
site, offset = 0x80600000 + index * 4, layout[main] + index * 4
assert list(words[index + 1:index + 4]) == [dform(36, 3, 30, 400), 0x7c0000a6, dform(36, 0, 30, 404)]
text = 0x806d0000
code = [dform(37, 1, 1, -16), spr(0, 8), dform(36, 0, 1, 20), dform(14, 3, 0, 0)]
call = text + len(code) * 4
code.append(branch(call, 0x80227dd0, True))
code.extend([dform(32, 0, 1, 20), spr(0, 8, True), dform(14, 1, 1, 16), 0x4e800020])
resume = text + len(code) * 4
code.append(dform(36, 0, 1, -4))
pointer(code, 0, 0xa032)
code.extend([0x7c000124, dform(32, 0, 1, -4), words[index + 4]])
code.append(branch(text + len(code) * 4, site + 20))
slot = next(i for i in range(7) if not layout[36 + i])
payload = struct.pack('>' + 'I' * len(code), *code)
layout[slot], layout[18 + slot], layout[36 + slot] = len(image), text, len(payload)
image.extend(payload)
struct.pack_into('>I', image, offset, branch(site, text, True))
struct.pack_into('>I', image, offset + 16, branch(site + 16, resume))
image[:256] = struct.pack('>64I', *layout)
(output / 'fpr-init.dol').write_bytes(image)
generation = json.loads((source / 'generation.json').read_text())
generation.update(generatorSha256=sha(Path(__file__)), helperSha256=sha(helpers),
    parentGenerationSha256=sha(source / 'generation.json'), parentHarnessSha256=sha(source / 'fpr-init.dol'),
    nativeInputsSha256=sha(inputs_path), harnessSha256=hashlib.sha256(image).hexdigest(),
    di86Call={'site': site, 'offset': offset, 'text': text, 'call': call, 'target': 0x80227dd0,
        'resume': resume, 'replayedWord': words[index + 4], 'slot': slot, 'bytes': len(payload)})
generation['records'][7]['kind'] = 'DI86_async'
generation['limits'] = ['Whole original SC/DI OPEN then fn80227DD0 with measured higher callback0; original SDK builds request and callback state.',
    'API return/MSR recorded before synthetic IRQ re-enable A032 for finite guest wait; no forced DI result/callback/state/FD.',
    'Isolated original SDK CPU oracle, lab thread/arena/emulator settings, not physical drive/cycles or whole retail game.']
(output / 'generation.json').write_text(json.dumps(generation, indent=2) + '\n')
print('Prepared original DI86/callback0; actual API captured BEFORE lab IRQ re-enable')

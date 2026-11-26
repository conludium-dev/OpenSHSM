"""Validate whole original SISetXY return, polling register and SDK mirror."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-si-xy')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation_path = output / 'generation.json'
capture_path = output / 'fpr-init-true-dolphin.json'
generation = json.loads(generation_path.read_text())
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert capture['records'] == len(generation['records']) == 16 and capture['accurateCache'] == 'True'
assert 'Dolphin.Core.CPUCore=0' in capture['arguments'] and '-v Null' in capture['arguments']
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / 'run_si_xy_dolphin.ps1')
for key, name in [('generatorSha256', 'build_si_xy_dolphin.py'), ('baseGeneratorSha256', 'build_template_copy_dolphin.py'),
                  ('helperSha256', 'build_dolphin_probe.py'), ('baseRunnerSha256', 'run_dolphin_probe.ps1')]:
    assert generation[key] == sha(experiment / name)
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert generation['originalSha256'] == sha(original_path)
original, image = original_path.read_bytes(), (output / 'fpr-init.dol').read_bytes()
patch = generation['exitPatchOffset']
assert generation['storeAddress'] == 0x8020feb0 and generation['exitPatchAddress'] == 0x8020ff08
assert generation['storeTarget'] == 0xcd006430
assert struct.unpack_from('>I', original, patch)[0] == 0x4e800020
assert {i for i in range(256, len(original)) if original[i] != image[i]} <= set(range(patch, patch + 4))
word = struct.unpack_from('>I', image, patch)[0]
assert word >> 26 == 18 and word & 3 == 0
displacement = word & 0x03fffffc
if displacement & 0x02000000:
    displacement -= 0x04000000
observer = 0x8020ff08 + displacement
layout = struct.unpack('>64I', image[:256])
section = next(i for i in range(7) if layout[18 + i] <= observer < layout[18 + i] + layout[36 + i])
assert struct.unpack_from('>I', image, layout[section] + observer - layout[18 + section])[0] == 0x907e0018
data = base64.b64decode(capture['data'])
assert len(data) == 16 * 736
values = []
for case in generation['records']:
    index = case['index']
    row = data[index * 736:(index + 1) * 736]
    assert row[:16] == b'OSHSM_PPC_DLP001'
    assert struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    result, raw, mirror, msr = struct.unpack_from('>4I', row, 24)
    expected = (case['mirrorBefore'] & 0xfc0000ff) | (case['x'] << 16) | (case['y'] << 8)
    assert result == mirror == raw == expected and msr == 0x2030
    values.append({**case, 'returnValue': result, 'pollRaw': raw, 'mirrorAfter': mirror, 'msr': msr})
(output / 'comparison.json').write_text(json.dumps({'result': 'WHOLE_ORIGINAL_SI_SET_XY16_VALIDATED', 'values': values,
    'captureSha256': sha(capture_path), 'generationSha256': sha(generation_path), 'verifierSha256': sha(Path(__file__)),
    'limits': generation['limits']}, indent=2) + '\n')
print('PASS16 whole original SISetXY: return/poll-register/mirror/MSR, preserved channel bits; no full SI initialization')

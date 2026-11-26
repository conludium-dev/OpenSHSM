"""Validate original MI store captures without assuming a register readback model."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-mi-mask')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation_path = output / 'generation.json'
generation = json.loads(generation_path.read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert capture['records'] == len(generation['records']) == 32 and capture['accurateCache'] == 'True'
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / 'run_mi_mask_dolphin.ps1')
for key, name in [('generatorSha256', 'build_mi_mask_dolphin.py'), ('baseGeneratorSha256', 'build_template_copy_dolphin.py'),
                  ('helperSha256', 'build_dolphin_probe.py'), ('baseRunnerSha256', 'run_dolphin_probe.ps1')]:
    assert generation[key] == sha(experiment / name)
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert generation['originalSha256'] == sha(original_path)
original, image = original_path.read_bytes(), (output / 'fpr-init.dol').read_bytes()
offset = generation['exitPatchOffset']
assert {i for i in range(256, len(original)) if original[i] != image[i]} <= set(range(offset, offset + 4))
assert struct.unpack_from('>I', original, offset - 4)[0] == generation['storeOpcode'] == 0xB0A4401C
assert generation['storeAddress'] == 0x802176E4 and generation['storeTarget'] == 0xCC00401C
data = base64.b64decode(capture['data'])
assert len(data) == 32 * 736
observations = []
for record in generation['records']:
    index = record['index']
    row = data[index * 736:(index + 1) * 736]
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>II', row, 16) == (0xC001CAFE, index)
    requested, mask_after, mask_before = struct.unpack_from('>3I', row, 24)
    cause_before, cause_after = struct.unpack_from('>2I', row, 56)
    assert requested == record['value'] and mask_before <= 65535 and mask_after <= 65535
    assert struct.unpack_from('>I', row, 44)[0] == 0x2030
    assert struct.unpack_from('>Q', row, 704)[0] & 0xFFFFFFFF == record['ni'] * 4
    observations.append({'index': index, 'requested': requested, 'priorSeed': record['priorMask'],
                         'maskBefore': mask_before, 'maskAfter': mask_after, 'causeBefore': cause_before, 'causeAfter': cause_after, 'ni': record['ni']})
readbacks = {value: sorted({row['maskAfter'] for row in observations if row['requested'] == value}) for value in (0, 1, 31, 65535)}
assert all(len(values) == 1 for values in readbacks.values())
report = {'result': 'ORIGINAL_MI_MASK_STORE32_OBSERVATIONS_VALIDATED', 'cases': 32, 'observations': observations,
          'readbacks': readbacks, 'captureSha256': sha(capture_path), 'generationSha256': sha(generation_path), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Original sth unchanged, adjacent BLR observer patch and synthetic mask/register/NI fixtures.',
                     'Observed register overwrite for selected values only; no protection faults, general MI behavior, interrupt delivery or physical Wii claim.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS32 original MI mask observations/readbacks:', readbacks)

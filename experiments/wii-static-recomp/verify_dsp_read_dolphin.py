"""Validate isolated original DSP read and its private capture provenance."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-dsp-read')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation_path = output / 'generation.json'
generation = json.loads(generation_path.read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert capture['records'] == len(generation['records']) == 16 and capture['accurateCache'] == 'True'
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / 'run_dsp_read_dolphin.ps1')
for key, name in [('generatorSha256', 'build_dsp_read_dolphin.py'), ('baseGeneratorSha256', 'build_template_copy_dolphin.py'),
                  ('helperSha256', 'build_dolphin_probe.py'), ('baseRunnerSha256', 'run_dolphin_probe.ps1')]:
    assert generation[key] == sha(experiment / name)
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert generation['originalSha256'] == sha(original_path)
original, image = original_path.read_bytes(), (output / 'fpr-init.dol').read_bytes()
offset = generation['exitPatchOffset']
assert {i for i in range(256, len(original)) if original[i] != image[i]} <= set(range(offset, offset + 4))
assert struct.unpack_from('>I', original, offset - 4)[0] == generation['storeOpcode'] == 0xA0A5500A
assert generation['storeAddress'] == 0x802176F4 and generation['storeTarget'] == 0xCC00500A
data = base64.b64decode(capture['data'])
assert len(data) == 16 * 736
observations = []
for record in generation['records']:
    index = record['index']
    row = data[index * 736:(index + 1) * 736]
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>II', row, 16) == (0xC001CAFE, index)
    value = struct.unpack_from('>I', row, 24)[0]
    cause_before, cause_after = struct.unpack_from('>2I', row, 56)
    assert value <= 65535 and struct.unpack_from('>I', row, 44)[0] == 0x2030
    assert struct.unpack_from('>Q', row, 704)[0] & 0xFFFFFFFF == record['ni'] * 4
    observations.append({'index': index, 'value': value, 'causeBefore': cause_before, 'causeAfter': cause_after, 'ni': record['ni']})
report = {'result': 'ORIGINAL_DSP_READ16_OBSERVATIONS_VALIDATED', 'cases': 16, 'observations': observations,
          'readValues': sorted({row['value'] for row in observations}), 'captureSha256': sha(capture_path),
          'generationSha256': sha(generation_path), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Unseeded Dolphin loader state, not full preceding original startup or physical Wii.',
                     'No DSP write, interrupt, DMA, mailbox protocol or audio verification.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS16 original DSP reads:', report['readValues'])

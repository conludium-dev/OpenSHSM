"""Verify unchanged original selection instructions and capture provenance."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-exi-select')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation_path, capture_path = output / 'generation.json', output / 'fpr-init-true-dolphin.json'
generation = json.loads(generation_path.read_text())
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert capture['records'] == len(generation['records']) == 16 and capture['accurateCache'] == 'True'
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / 'run_exi_select_dolphin.ps1')
for key, name in [('generatorSha256', 'build_exi_select_dolphin.py'), ('baseGeneratorSha256', 'build_template_copy_dolphin.py'),
                  ('helperSha256', 'build_dolphin_probe.py'), ('baseRunnerSha256', 'run_dolphin_probe.ps1')]:
    assert generation[key] == sha(experiment / name)
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert generation['originalSha256'] == sha(original_path)
original, image = original_path.read_bytes(), (output / 'fpr-init.dol').read_bytes()
offset = generation['exitPatchOffset']
assert generation['exitPatchAddress'] == 0x8020e3e4
assert struct.unpack_from('>I', original, offset - 0x24)[0] == generation['storeOpcode'] == 0x80646800
assert generation['storeAddress'] == 0x8020e3c0 and generation['storeTarget'] == 0xcd006800
assert {i for i in range(256, len(original)) if original[i] != image[i]} <= set(range(offset, offset + 4))
data = base64.b64decode(capture['data'])
assert len(data) == 16 * 736
observations = []
for record in generation['records']:
    index = record['index']
    row = data[index * 736:(index + 1) * 736]
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>II', row, 16) == (0xc001cafe, index)
    value, after, before = struct.unpack_from('>3I', row, 24)
    cause_before, cause_after = struct.unpack_from('>2I', row, 56)
    assert struct.unpack_from('>I', row, 44)[0] == 0x2030
    assert struct.unpack_from('>Q', row, 704)[0] & 0xffffffff == record['ni'] * 4
    assert value == (before & 0x405) | (record['clock'] << 4) | (1 << (record['device'] + 7))
    observations.append({**record, 'before': before, 'value': value, 'after': after, 'causeBefore': cause_before, 'causeAfter': cause_after})
report = {'result': 'ORIGINAL_EXI_SELECT16_OBSERVATIONS_VALIDATED', 'cases': 16, 'observations': observations,
          'captureSha256': sha(capture_path), 'generationSha256': sha(generation_path), 'verifierSha256': sha(Path(__file__)), 'limits': generation['limits']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('Original EXISelect:', observations[:4])

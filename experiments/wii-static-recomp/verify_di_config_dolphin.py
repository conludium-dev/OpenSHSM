"""Validate the original DI getter and captured raw/config-byte values."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-di-config')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation_path, capture_path = output / 'generation.json', output / 'fpr-init-true-dolphin.json'
generation = json.loads(generation_path.read_text())
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert capture['records'] == len(generation['records']) == 16 and capture['accurateCache'] == 'True'
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / 'run_di_config_dolphin.ps1')
for key, name in [('generatorSha256', 'build_di_config_dolphin.py'), ('baseGeneratorSha256', 'build_template_copy_dolphin.py'),
                  ('helperSha256', 'build_dolphin_probe.py'), ('baseRunnerSha256', 'run_dolphin_probe.ps1')]:
    assert generation[key] == sha(experiment / name)
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert generation['originalSha256'] == sha(original_path)
original, image = original_path.read_bytes(), (output / 'fpr-init.dol').read_bytes()
offset = generation['exitPatchOffset']
assert generation['exitPatchAddress'] == 0x80211d0c
assert generation['storeAddress'] == 0x80211d00 and generation['storeTarget'] == 0xcd006024
assert struct.unpack_from('>3I', original, offset - 12) == (0x3c60cd00, 0x80036024, 0x5403063e)
assert {i for i in range(256, len(original)) if original[i] != image[i]} <= set(range(offset, offset + 4))
data = base64.b64decode(capture['data'])
assert len(data) == 16 * 736
values = []
for index in range(16):
    row = data[index * 736:(index + 1) * 736]
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    result, raw = struct.unpack_from('>2I', row, 24)
    assert result == raw & 255 and raw == 1
    values.append({'index': index, 'raw': raw, 'returnValue': result})
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_DI_CONFIG16_READS_VALIDATED', 'values': values,
    'captureSha256': sha(capture_path), 'generationSha256': sha(generation_path), 'verifierSha256': sha(Path(__file__)),
    'limits': generation['limits']}, indent=2) + '\n')
print('PASS16 original DI config getter: raw1/return1; vendorFF differs')

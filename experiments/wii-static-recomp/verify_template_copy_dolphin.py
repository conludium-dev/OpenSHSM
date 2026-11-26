"""Check original store and memcpy results against byte-exact DOL template variants."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-template-copy')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert capture['records'] == len(generation['records']) == 16 and capture['accurateCache'] == 'True'
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / 'run_template_copy_dolphin.ps1')
assert generation['generatorSha256'] == sha(experiment / 'build_template_copy_dolphin.py')
assert generation['helperSha256'] == sha(experiment / 'build_dolphin_probe.py')
assert generation['baseRunnerSha256'] == sha(experiment / 'run_dolphin_probe.ps1')
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert generation['originalSha256'] == sha(original_path)
original = original_path.read_bytes()
image = (output / 'fpr-init.dol').read_bytes()
offset = generation['exitPatchOffset']
assert {index for index in range(256, len(original)) if original[index] != image[index]} <= set(range(offset, offset + 4))
assert struct.unpack_from('>I', original, offset - 4)[0] == generation['storeOpcode']
header = struct.unpack('>64I', original[:256])
address = generation['template']
length = generation['templateBytes']
section = next(index for index in range(7) if header[18 + index] <= address < header[18 + index] + header[36 + index])
start = header[section] + address - header[18 + section]
template = original[start:start + length]
data = base64.b64decode(capture['data'])
assert len(data) == 16 * 736
observations = []
for record in generation['records']:
    index = record['index']
    row = data[index * 736:(index + 1) * 736]
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>II', row, 16) == (0xc001cafe, index)
    stored, returned, readback = struct.unpack_from('>III', row, 24)
    assert stored == readback == record['value'] and returned == record['destination']
    expected = bytearray(template)
    struct.pack_into('>I', expected, generation['storeTarget'] - address, record['value'])
    copied = row[192:192 + length]
    assert copied == expected, (index, copied.hex(), expected.hex())
    observations.append({'index': index, 'patchedWord': stored, 'memcpyReturn': returned,
                         'copiedSha256': hashlib.sha256(copied).hexdigest()})
report = {'result': 'ORIGINAL_STORE_AND_MEMCPY_16_TEMPLATE_VARIANTS_BYTE_EXACT',
          'cases': 16, 'templateBytes': length, 'copiedBytesCompared': length * 16,
          'observations': observations, 'captureSha256': sha(capture_path), 'generationSha256': sha(output / 'generation.json'),
          'originalTemplateSha256': hashlib.sha256(template).hexdigest(), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Original store and memcpy unchanged; adjacent exit observer patch and synthetic register/MSR/HID0 fixtures.',
                     'Cached CPU-visible template mutation/copy verified in Dolphin, not physical Wii cache timing.',
                     'Ordinary scratch destination, not real exception-vector addresses; no relocated handler execution or full OS loop proof.',
                     'Native code-write adaptation/integration and complete post-clock endpoint remain unverified.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS original store/memcpy16variants×152bytes=2432byte comparisons; native mutable templates/relocation pending')

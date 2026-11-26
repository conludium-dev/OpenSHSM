"""Verify original SI idle-loop and control-write observations/provenance."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-si-idle')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation_path, capture_path = output / 'generation.json', output / 'fpr-init-true-dolphin.json'
generation = json.loads(generation_path.read_text())
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert capture['records'] == len(generation['records']) == 16 and capture['accurateCache'] == 'True'
assert 'Dolphin.Core.CPUCore=0' in capture['arguments'] and '-v Null' in capture['arguments']
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / 'run_si_idle_dolphin.ps1')
for key, name in [('generatorSha256', 'build_si_idle_dolphin.py'), ('baseGeneratorSha256', 'build_template_copy_dolphin.py'),
                  ('helperSha256', 'build_dolphin_probe.py'), ('baseRunnerSha256', 'run_dolphin_probe.ps1')]:
    assert generation[key] == sha(experiment / name)
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert generation['originalSha256'] == sha(original_path)
original, image = original_path.read_bytes(), (output / 'fpr-init.dol').read_bytes()
layout, generated = struct.unpack('>64I', original[:256]), struct.unpack('>64I', image[:256])

def offset(address, header=layout):
    section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
    return header[section] + address - header[18 + section]

def target(address, header=layout):
    word = struct.unpack_from('>I', image, offset(address, header))[0]
    assert word >> 26 == 18 and word & 3 == 0
    displacement = word & 0x03fffffc
    if displacement & 0x02000000:
        displacement -= 0x04000000
    return address + displacement

assert generation['storeAddress'] == 0x8020fc94 and generation['storeTarget'] == 0xcd006434
assert generation['exitPatchAddress'] == 0x8020fcb4
assert struct.unpack_from('>9I', original, offset(0x8020fc94)) == (
    0x3c60cd00, 0x80036434, 0x540007ff, 0x4082fff8, 0x3c60cd00, 0x3c008000, 0x3c808021, 0x90036434, 0x3884f850)
allowed = set(range(offset(0x8020fc9c), offset(0x8020fc9c) + 4)) | set(range(offset(0x8020fcb4), offset(0x8020fcb4) + 4))
assert {i for i in range(256, len(original)) if original[i] != image[i]} <= allowed
observer = target(0x8020fc9c)
assert observer == generation['readObserverAddress']
assert struct.unpack_from('>2I', image, offset(observer, generated)) == (0x901e0018, 0x540007ff)
assert target(observer + 8, generated) == 0x8020fca0
exit_observer = target(0x8020fcb4)
assert struct.unpack_from('>I', image, offset(exit_observer, generated))[0] == 0x901e001c
data = base64.b64decode(capture['data'])
assert len(data) == 16 * 736
values = []
for index in range(16):
    row = data[index * 736:(index + 1) * 736]
    assert row[:16] == b'OSHSM_PPC_DLP001'
    assert struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    before, written, after, pi_before, pi_after = struct.unpack_from('>5I', row, 24)
    assert (before, written, after, pi_before, pi_after) == (0, 0x80000000, 0, 0x10000, 0x10000)
    values.append({'index': index, 'controlBefore': before, 'written': written, 'controlAfter': after,
        'piBefore': pi_before, 'piAfter': pi_after})
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_SI_IDLE_CONTROL16_VALIDATED', 'values': values,
    'captureSha256': sha(capture_path), 'generationSha256': sha(generation_path), 'verifierSha256': sha(Path(__file__)),
    'limits': generation['limits'] + ['No asserted TCINT or busy START event measured; writing80000000 to observed idle0 does not prove event-clearing semantics.']}, indent=2) + '\n')
print('PASS16 original SI idle0/write80000000/readback0; PI10000 unchanged; no busy/event-clearing proof')

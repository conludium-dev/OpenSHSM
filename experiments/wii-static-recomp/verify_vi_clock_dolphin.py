"""Check the raw VI clock observation and original sampling table calculation."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-vi-clock')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation_path = output / 'generation.json'
capture_path = output / 'fpr-init-true-dolphin.json'
generation = json.loads(generation_path.read_text())
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert capture['records'] == len(generation['records']) == 16
assert capture['accurateCache'] == 'True'
assert 'Dolphin.Core.CPUCore=0' in capture['arguments'] and '-v Null' in capture['arguments']
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / 'run_vi_clock_dolphin.ps1')
for key, name in [('generatorSha256', 'build_vi_clock_dolphin.py'), ('baseGeneratorSha256', 'build_template_copy_dolphin.py'),
                  ('helperSha256', 'build_dolphin_probe.py'), ('baseRunnerSha256', 'run_dolphin_probe.ps1')]:
    assert generation[key] == sha(experiment / name)
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert generation['originalSha256'] == sha(original_path)
original = original_path.read_bytes()
image = (output / 'fpr-init.dol').read_bytes()
header = struct.unpack('>64I', original[:256])
image_header = struct.unpack('>64I', image[:256])

def offset(address, layout=header):
    section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
    return layout[section] + address - layout[18 + section]

def branch_target(address):
    word = struct.unpack_from('>I', image, offset(address))[0]
    assert word >> 26 == 18 and word & 3 == 0
    displacement = word & 0x03fffffc
    if displacement & 0x02000000:
        displacement -= 0x04000000
    return address + displacement

allowed = set(range(offset(0x80210624), offset(0x80210624) + 4)) | set(range(offset(0x8021063c), offset(0x8021063c) + 4))
assert {i for i in range(256, len(original)) if original[i] != image[i]} <= allowed
assert struct.unpack_from('>3I', original, offset(0x80210618)) == (0x3c60cc00, 0x57a0103a, 0xa083206c)
assert struct.unpack_from('>I', original, offset(0x80210624))[0] == 0x7c650214
observer = branch_target(0x80210624)
assert observer == generation['readObserverAddress']
observer_offset = offset(observer, image_header)
assert struct.unpack_from('>2I', image, observer_offset) == (0x909e0018, 0x7c650214)
word = struct.unpack_from('>I', image, observer_offset + 8)[0]
displacement = word & 0x03fffffc
if displacement & 0x02000000:
    displacement -= 0x04000000
assert word >> 26 == 18 and word & 3 == 0 and observer + 8 + displacement == 0x80210628
assert generation['exitPatchAddress'] == 0x8021063c
assert struct.unpack_from('>I', original, offset(0x8021063c))[0] == 0x4bfff875
assert branch_target(0x8021063c) < observer
data = base64.b64decode(capture['data'])
assert len(data) == 16 * 736
values = []
for case in generation['records']:
    index, rate, table = case['index'], case['rate'], case['tableAddress']
    row = data[index * 736:(index + 1) * 736]
    assert row[:16] == b'OSHSM_PPC_DLP001'
    assert struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    raw, x, y, clock_bit, table_x = struct.unpack_from('>5I', row, 24)
    expected_x, expected_y = struct.unpack_from('>HB', original, offset(table + rate * 4))
    assert raw == 1 and clock_bit == raw & 1
    assert table_x == expected_x and x == (clock_bit + 1) * expected_x and y == expected_y
    values.append({'index': index, 'rate': rate, 'tableAddress': table, 'clockRaw': raw, 'clockBit': clock_bit, 'x': x, 'y': y})
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_VI_CLOCK_AND_SAMPLING_BLOCK16_VALIDATED', 'values': values,
    'captureSha256': sha(capture_path), 'generationSha256': sha(generation_path), 'verifierSha256': sha(Path(__file__)),
    'vendorViSha256': sha(Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime/src/hw/hw_vi.cpp')),
    'limits': generation['limits']}, indent=2) + '\n')
print('PASS16 original VI clock/sampling calculation: loader raw1, own-DOL NTSC/PAL table outputs; vendor zero would halve X; no SI calls accepted')

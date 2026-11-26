"""Verify original HID4 function observations and its reference BAT memory effect."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-hid4-probe')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert capture['records'] == len(generation['records']) == 8 and capture['accurateCache'] == 'True'
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / 'run_hid4_dolphin.ps1')
assert generation['baseRunnerSha256'] == sha(experiment / 'run_dolphin_probe.ps1')
assert generation['generatorSha256'] == sha(experiment / 'build_hid4_dolphin.py')
assert generation['helperSha256'] == sha(experiment / 'build_dolphin_probe.py')
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert hashlib.sha256(original).hexdigest() == generation['originalSha256']
image = (output / 'fpr-init.dol').read_bytes()
assert image[256:len(original)] == original[256:]
data = base64.b64decode(capture['data'])
assert len(data) == 8 * 736
observations = []
for record in generation['records']:
    index = record['index']
    row = data[index * 736:(index + 1) * 736]
    assert row[:16] == b'OSHSM_PPC_DLP001'
    assert struct.unpack_from('>II', row, 16) == (0xc001cafe, index)
    gpr = list(struct.unpack_from('>32I', row, 32))
    cr, lr, ctr, xer, hid2, hid0, msr = struct.unpack_from('>7I', row, 160)
    expected = record['initialGpr'].copy()
    expected[0] = record['expectedLr']
    assert gpr == expected, (index, [(i, hex(a), hex(b)) for i, (a, b) in enumerate(zip(gpr, expected)) if a != b])
    expected_cr = (record['cr'] & 0x0fffffff) | ((8 | (record['xer'] >> 31)) << 28)
    assert [cr, lr, ctr, xer, hid2, hid0, msr] == [expected_cr, record['expectedLr'], record['ctr'], record['xer'], 0xa0000000, 0, 0x2030]
    hid4, alias, dbat3u, dbat3l, dbat4u, dbat4l = struct.unpack_from('>6I', row, 712)
    assert hid4 == record['argument'] and alias == record['expectedAlias'], (index, hex(hid4), hex(alias))
    assert [dbat3u, dbat3l, dbat4u, dbat4l] == [0xa0000002, 0x00700022, 0xa0000002, 0x00720022]
    observations.append({'index': index, 'hid4': hid4, 'aliasValue': alias, 'gpr': gpr, 'cr': cr,
                         'lr': lr, 'ctr': ctr, 'xer': xer, 'msr': msr, 'dbat3': [dbat3u, dbat3l], 'dbat4': [dbat4u, dbat4l]})
report = {'result': 'ORIGINAL_HID4_FUNCTION_AND_DOLPHIN_SBE_ALIAS_VERIFIED', 'cases': 8,
          'captureSha256': sha(capture_path), 'generationSha256': sha(output / 'generation.json'),
          'verifierSha256': sha(Path(__file__)), 'observations': observations,
          'limits': ['Original80-byte function and all original DOL game bytes unchanged; synthetic measurement entry and BAT setup.',
                     'High-bit-set arguments avoid the original diagnostic OSReport branch; low-high-bit branch remains unverified.',
                     'Competing BAT3/BAT4 alias demonstrates Dolphin reference priority/SBE effect, not physical Wii overlapping-BAT semantics.',
                     'No native HID4/MMU lowering activation or full live boot acceptance; L2/ST0 effects remain unverified.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS original HID4 function8cases/GPR-flags-ABI; SBE changes actual alias read; native MMU still pending')

"""Validate original reset execution; this gate does not accept a native implementation."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-performance-probe')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert capture['records'] == len(generation['records']) == 8 and capture['accurateCache'] == 'True'
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / 'run_performance_dolphin.ps1')
assert generation['baseRunnerSha256'] == sha(experiment / 'run_dolphin_probe.ps1')
assert generation['generatorSha256'] == sha(experiment / 'build_performance_dolphin.py')
assert generation['helperSha256'] == sha(experiment / 'build_dolphin_probe.py')
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
original = original_path.read_bytes()
assert generation['originalSha256'] == sha(original_path)
image = (output / 'fpr-init.dol').read_bytes()
offset = generation['exitPatchOffset']
assert {i for i in range(256, len(original)) if image[i] != original[i]} <= set(range(offset, offset + 4))
assert generation['registers'] == [952, 956, 953, 954, 957, 958]
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
    expected[3] = 0
    assert gpr == expected, (index, [(i, hex(a), hex(b)) for i, (a, b) in enumerate(zip(gpr, expected)) if a != b])
    assert [cr, lr, ctr, xer, hid2, hid0, msr] == [record['cr'], 0x802113d8, record['ctr'], record['xer'], 0xa0000000, 0x4000, 0x2030]
    registers = list(struct.unpack_from('>6I', row, 712))
    assert registers == [0] * 6, (index, registers)
    observations.append({'index': index, 'gpr': gpr, 'cr': cr, 'lr': lr, 'ctr': ctr, 'xer': xer, 'msr': msr, 'registers': registers})
report = {'result': 'ORIGINAL_SIX_REGISTER_RESET_DOLPHIN_EXECUTION_MATCH', 'cases': 8,
          'captureSha256': sha(capture_path), 'generationSha256': sha(output / 'generation.json'),
          'verifierSha256': sha(Path(__file__)), 'observations': observations,
          'limits': ['Original48-byte reset sequence and six8-byte setters unchanged; observer exit patch after sequence.',
                     'Synthetic frozen initial MMCR0 and seeded counters, EE=0; original sequence writes zero to all six.',
                     'Only final register readback/GPR/CR/LR/CTR/XER/MSR checked; counting, interrupts, aliases, physical Wii and full boot remain unverified.',
                     'Native reset implementation and live quarantine activation not accepted by this gate.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS original six-register reset:8Dolphin cases; register readback/GPR/CR/LR/CTR/XER/MSR; native not yet accepted')

"""Validate and retain loader inputs separately from original game behavior evidence."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-bat-seed')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert capture['records'] == 8 and generation['stride'] == 864 and capture['accurateCache'] == 'True'
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / 'run_bat_seed.ps1')
assert generation['baseRunnerSha256'] == sha(experiment / 'run_dolphin_probe.ps1')
assert generation['generatorSha256'] == sha(experiment / 'build_bat_seed.py')
assert generation['helperSha256'] == sha(experiment / 'build_dolphin_probe.py')
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert hashlib.sha256(original).hexdigest() == generation['originalSha256']
assert (output / 'fpr-init.dol').read_bytes()[256:len(original)] == original[256:]
data = base64.b64decode(capture['data'])
assert len(data) == 8 * 864
observations = []
for index in range(8):
    row = data[index * 864:(index + 1) * 864]
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>II', row, 16) == (0xc001cafe, index)
    observations.append(list(struct.unpack_from('>33I', row, 712)))
assert all(row == observations[0] for row in observations)
values = observations[0]
report = {'result': 'DOLPHIN_LOADER_BAT_INPUTS_OBSERVED', 'cases': 8, 'hid4': values[0],
          'ibat': [values[1 + index * 2:3 + index * 2] for index in range(8)],
          'dbat': [values[17 + index * 2:19 + index * 2] for index in range(8)],
          'captureSha256': sha(capture_path), 'generationSha256': sha(output / 'generation.json'), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Dolphin DOL loader inputs, not physical Wii power-on registers or original game initialization behavior.',
                     'Observer changes MSR to2030 and floating-point capture setup, but does not write BAT or HID4 registers.']}
(output / 'seed.json').write_text(json.dumps(report, indent=2) + '\n')
print('Observed loader HID4/BAT inputs:', hex(report['hid4']), report['ibat'], report['dbat'])

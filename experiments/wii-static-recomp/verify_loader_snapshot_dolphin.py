"""Verify provenance and repeated initial emulator loader snapshots without assuming an IOS."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-loader-snapshot')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
for key, filename in [('generatorSha256', 'build_loader_snapshot_dolphin.py'),
        ('parentSha256', 'build_si_query_dolphin.py'), ('helperSha256', 'build_dolphin_probe.py'),
        ('wrapperSha256', 'run_loader_snapshot_dolphin.ps1'), ('baseRunnerSha256', 'run_dolphin_probe.ps1')]:
    assert generation[key] == sha(experiment / filename)
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
image = (output / 'fpr-init.dol').read_bytes()
assert generation['originalSha256'] == hashlib.sha256(original).hexdigest()
assert generation['harnessSha256'] == sha(output / 'fpr-init.dol') == capture['harnessSha256'].lower()
assert capture['scriptSha256'].lower() == generation['wrapperSha256']
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
assert generation['patches'] == [] and image[256:len(original)] == original[256:]
assert capture['records'] == 16 and capture['accurateCache'] == 'True'
for flag in ('Dolphin.Core.CPUCore=0', '-v Null', 'dolphin-loader-snapshot-user'):
    assert flag in capture['arguments']
data = base64.b64decode(capture['data'])
assert len(data) == 16 * 736
states = []
for index, case in enumerate(generation['records']):
    row = data[index * 736:(index + 1) * 736]
    assert row[:16] == b'OSHSM_PPC_DLP001'
    assert struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    values = struct.unpack_from('>' + 'I' * len(case['addresses']), row, 24)
    states.append(dict(zip(case['addresses'], values)))
assert all(state == states[0] for state in states)
state = states[0]
assert 0x90000000 <= state[0x3124] < state[0x3128] <= state[0x3120] <= 0x94000000
assert state[0x3130] == state[0x3128] and state[0x3134] == state[0x3120]
assert state[0x3148] == state[0x3120] < state[0x314c] <= 0x94000000
(output / 'comparison.json').write_text(json.dumps({
    'result': 'DIRECT_DOL_EMULATOR_LOADER16_READ_ONLY_SNAPSHOTS_PASS',
    'generationSha256': sha(output / 'generation.json'), 'captureSha256': sha(capture_path),
    'verifierSha256': sha(Path(__file__)),
    'fields': {f'{address:08x}': f'{value:08x}' for address, value in state.items()},
    'limits': generation['limits'],
}, indent=2) + '\n')
print('PASS16stable initial Dolphin loader snapshots: ' + json.dumps({
    f'{address:04x}': f'{state[address]:08x}' for address in (0x3120, 0x3124, 0x3128, 0x3130, 0x3134, 0x3140)}))

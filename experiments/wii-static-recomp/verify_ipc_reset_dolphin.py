"""Verify write-only mask reset via readable control and ARM-message observations."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-ipc-reset')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert capture['records'] == len(generation['records']) == 32 and capture['accurateCache'] == 'True'
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / 'run_ipc_reset_dolphin.ps1')
for key, name in [('generatorSha256', 'build_ipc_reset_dolphin.py'), ('helperSha256', 'build_dolphin_probe.py'),
                  ('baseRunnerSha256', 'run_dolphin_probe.ps1'), ('baseGeneratorSha256', 'build_template_copy_dolphin.py')]:
    assert generation[key] == sha(experiment / name)
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert generation['originalSha256'] == sha(original_path)
original, image = original_path.read_bytes(), (output / 'fpr-init.dol').read_bytes()
offset = generation['exitPatchOffset']
assert {i for i in range(256, len(original)) if original[i] != image[i]} <= set(range(offset, offset + 4))
assert struct.unpack_from('>I', original, offset - 4)[0] == generation['storeOpcode'] == 0x90030034
assert generation['storeAddress'] == 0x802175d4 and generation['storeTarget'] == 0xcd000034
data = base64.b64decode(capture['data'])
assert len(data) == 32 * 736
observations = []
for record in generation['records']:
    index = record['index']
    row = data[index * 736:(index + 1) * 736]
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>II', row, 16) == (0xc001cafe, index)
    requested, control_after, control_before, arm_before, arm_after, msr = struct.unpack_from('>6I', row, 24)
    assert requested == record['value'] and control_before == record['priorControl']
    expected = 0 if requested & 0x40000000 else control_before
    assert control_after == expected, (index, hex(control_before), hex(control_after), hex(expected))
    assert arm_before == arm_after == 0 and msr == 0x2030
    assert (struct.unpack_from('>Q', row, 704)[0] & 0xffffffff) == record['ni'] * 4
    cause_before, cause_after = struct.unpack_from('>2I', row, 56)
    observations.append({'index': index, 'requestedMask': requested, 'controlBefore': control_before,
                         'controlAfter': control_after, 'armMessageBefore': arm_before, 'armMessageAfter': arm_after,
                         'causeBefore': cause_before, 'causeAfter': cause_after, 'msr': msr, 'fpscr': record['ni'] * 4})
report = {'result': 'ORIGINAL_IPC_MASK32_EE0_CONTROL_RESET_BIT_MATCH', 'cases': 32,
          'observations': observations, 'captureSha256': sha(capture_path), 'generationSha256': sha(output / 'generation.json'),
          'verifierSha256': sha(Path(__file__)),
          'limits': ['Original store/NI setter unchanged; adjacent observer and synthetic mask/control/register setup.',
                     'Control-IY flags reset with bit40000000 and persist without it; ARM message zero remains zero.',
                     'Mask/PPCMSG write-only state, nonzero messages, IOS/queued events/external delivery/physical Wii unverified.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS32originalIPC-mask control-reset/NI0-NI1/EE0cases; full IOS/events unverified')

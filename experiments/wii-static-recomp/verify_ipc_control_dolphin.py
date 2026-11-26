"""Verify captured original indexed control-store and X2 observations."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-ipc-control')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert capture['records'] == len(generation['records']) == 8 and capture['accurateCache'] == 'True'
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / 'run_ipc_control_dolphin.ps1')
for key, name in [('generatorSha256', 'build_ipc_control_dolphin.py'), ('helperSha256', 'build_dolphin_probe.py'),
                  ('baseRunnerSha256', 'run_dolphin_probe.ps1'), ('baseGeneratorSha256', 'build_template_copy_dolphin.py'),
                  ('pendingGeneratorSha256', 'build_ipc_pending_dolphin.py')]:
    assert generation[key] == sha(experiment / name)
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
original, image = original_path.read_bytes(), (output / 'fpr-init.dol').read_bytes()
assert hashlib.sha1(original).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
assert generation['originalSha256'] == sha(original_path)
offset = generation['exitPatchOffset']
assert {i for i in range(256, len(original)) if original[i] != image[i]} <= set(range(offset, offset + 4))
assert struct.unpack_from('>I', original, offset - 4)[0] == generation['storeOpcode'] == 0x7C83012E
assert (generation['storeAddress'], generation['storeTarget'], generation['exitPatchAddress']) == (0x80241C38, 0xCD000004, 0x80241C3C)
assert generation['requestPath'] == '/dev/openshsm_missing'
data = base64.b64decode(capture['data'])
assert len(data) == 8 * 736
observations = []
for record in generation['records']:
    index = record['index']
    row = data[index * 736:(index + 1) * 736]
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>II', row, 16) == (0xC001CAFE, index)
    value, after, before, message_before, message_after, msr = struct.unpack_from('>6I', row, 24)
    cause_before, cause_after, ack_timeout, reply_timeout, later, message_later, command, result, fd, prior_command = struct.unpack_from('>10I', row, 56)
    x2_after = struct.unpack_from('>I', row, 96)[0]
    assert value == record['value'] and before == (0x34 if record['stage'] == 'reply' else 0x32)
    assert after == later == value & 0x30
    assert message_before == message_after == message_later == (record['request'] if record['stage'] == 'reply' else 0)
    assert ack_timeout == reply_timeout == 0 and command == prior_command == 8 and result == 0xFFFFFFFA and fd == 1
    assert x2_after == 0x38 and msr == 0x2030
    assert struct.unpack_from('>Q', row, 704)[0] & 0xFFFFFFFF == record['ni'] * 4
    observations.append({'index': index, 'stage': record['stage'], 'ni': record['ni'], 'value': value,
                         'controlBefore': before, 'controlAfter': after, 'controlLater': later,
                         'armMessage': message_after, 'x2Write': 0x38, 'controlAfterX2': x2_after,
                         'causeBefore': cause_before, 'causeAfter': cause_after})
report = {'result': 'ORIGINAL_CONTROL_W1C_AND_X2_8_OBSERVATIONS_PASS', 'cases': 8, 'observations': observations,
          'captureSha256': sha(capture_path), 'generationSha256': sha(output / 'generation.json'),
          'verifierSha256': sha(Path(__file__)),
          'limits': ['Original indexed store unchanged; adjacent BLR redirected to private observer.',
                     'Read-only missing-device fixture and emulator IOS, not physical Wii or full retail boot.',
                     'Immediate/delayed control projection only; IRQFLAG remains latched during observation.',
                     'Second X2 write is measurement code; native producer/IRQ/cache/general IOS unverified.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS8 original IPC control clear/X2 observations, NI0/1; native backend pending')

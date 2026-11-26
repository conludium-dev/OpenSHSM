"""Verify original reset before/after asynchronous reply without inferring queue deletion."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-ipc-pending')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert capture['records'] == len(generation['records']) == 8 and capture['accurateCache'] == 'True'
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / 'run_ipc_pending_dolphin.ps1')
for key, name in [('generatorSha256', 'build_ipc_pending_dolphin.py'), ('helperSha256', 'build_dolphin_probe.py'),
                  ('baseRunnerSha256', 'run_dolphin_probe.ps1'), ('baseGeneratorSha256', 'build_template_copy_dolphin.py')]:
    assert generation[key] == sha(experiment / name)
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert generation['originalSha256'] == sha(original_path)
original, image = original_path.read_bytes(), (output / 'fpr-init.dol').read_bytes()
offset = generation['exitPatchOffset']
assert {i for i in range(256, len(original)) if original[i] != image[i]} <= set(range(offset, offset + 4))
assert struct.unpack_from('>I', original, offset - 4)[0] == generation['storeOpcode'] == 0x90030034
assert (generation['storeAddress'], generation['storeTarget'], generation['exitPatchAddress']) == (0x802175d4, 0xcd000034, 0x802175d8)
assert generation['requestPath'] == '/dev/openshsm_missing' and generation['delayedLoopIterations'] == 50000
data = base64.b64decode(capture['data'])
assert len(data) == 8 * 736
observations = []
for record in generation['records']:
    index = record['index']
    row = data[index * 736:(index + 1) * 736]
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>II', row, 16) == (0xc001cafe, index)
    requested, immediate_control, before_control, before_message, immediate_message, msr = struct.unpack_from('>6I', row, 24)
    cause_before, cause_after, ack_timeout, reply_timeout, later_control, later_message, command, result, reply_fd, before_command = struct.unpack_from('>10I', row, 56)
    assert ack_timeout == reply_timeout == 0 and requested == record['value']
    reply = record['stage'] == 'reply'
    assert before_control == (0x34 if reply else 0x32)
    assert before_message == (record['request'] if reply else 0)
    reset = requested == 0x40000000
    assert immediate_control == (0 if reset else before_control)
    assert immediate_message == (0 if reset else before_message)
    expected_control = (0 if reply else 4) if reset else before_control
    expected_message = (0 if reply else record['request']) if reset else before_message
    assert (later_control, later_message) == (expected_control, expected_message)
    assert command == before_command == 8 and result == 0xfffffffa and reply_fd == 1
    assert msr == 0x2030 and (struct.unpack_from('>Q', row, 704)[0] & 0xffffffff) == record['ni'] * 4
    observations.append({'index': index, 'ni': record['ni'], 'stage': record['stage'], 'requestedMask': requested,
                         'request': record['request'], 'controlBefore': before_control, 'messageBefore': before_message,
                         'controlImmediate': immediate_control, 'messageImmediate': immediate_message,
                         'controlLater': later_control, 'messageLater': later_message,
                         'causeBefore': cause_before, 'causeAfter': cause_after, 'replyCommand': command, 'replyResult': -6})
report = {'result': 'ORIGINAL_IPC_RESET_PRESERVES_PENDING_REPLY_8_OBSERVATIONS', 'cases': 8, 'observations': observations,
          'captureSha256': sha(capture_path), 'generationSha256': sha(output / 'generation.json'), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Original store/NI setter unchanged; synthetic nonexistent-device read-only OPEN and bounded ACK/reply polling.',
                     'Observed immediate and later states; loop bounds do not prove precise TB timing, physical Wii or all IOS requests.',
                     'Kernel reply survives hardware reset in ACK cases; delivered reply clears in reply cases.',
                     'Native transport/queues/full reset/GPIO/device integration and ordinary boot activation unverified.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS8originalACK/reply reset/noreset cases; delayedreplysurviveshardware reset, NI0-NI1')

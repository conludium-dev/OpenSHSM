"""Verify original control writes and immediate/delayed IRQFLAG-clear effects."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'verify_ipc_control_dolphin.py'
body = parent.read_text().replace('dolphin-ipc-control', 'dolphin-ipc-irq')
body = body.replace('build_ipc_control_dolphin.py', 'build_ipc_irq_dolphin.py')
body = body.replace('run_ipc_control_dolphin.ps1', 'run_ipc_irq_dolphin.ps1')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/dolphin-ipc-irq')
generation = json.loads((output / 'generation.json').read_text())
assert generation['controlGeneratorSha256'] == hashlib.sha256((experiment / 'build_ipc_control_dolphin.py').read_bytes()).hexdigest()
capture = json.loads((output / 'fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
data = base64.b64decode(capture['data'])
path = output / 'comparison.json'
report = json.loads(path.read_text())
for row, record in zip(report['observations'], generation['records']):
    index = row['index']
    immediate_cause, immediate_control, immediate_message, later_cause, later_control, later_message = struct.unpack_from('>6I', data, index * 736 + 100)
    ack = row['stage'] == 'ack'
    assert row['causeBefore'] == 0x10000 and row['causeAfter'] == 0x14000
    assert immediate_cause == 0x14000 and later_cause == (0x14000 if ack else 0x10000)
    assert immediate_control == later_control == (0x3C if ack else 0x38)
    assert immediate_message == later_message == record['request']
    row.update({'causeAfterFlagClear': immediate_cause, 'controlAfterFlagClear': immediate_control,
                'messageAfterFlagClear': immediate_message, 'causeAfterDelay': later_cause,
                'controlAfterDelay': later_control, 'messageAfterDelay': later_message,
                'request': record['request']})
report['result'] = 'ORIGINAL_IRQFLAG_CLEAR_IMMEDIATE_DELAYED_ACK_REPLY8_OBSERVATIONS_PASS'
report['baseVerifierSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Original indexed control store unchanged; IRQFLAG clear and observation delay are measurement code.',
                    'ACK clear releases queued reply; PI update is deferred in emulator. Delay50000 is a fixture bound, not physical timing.',
                    'Read-only missing-device request, EE0/NI0-1, not hardware Wii or retail boot/vector execution.',
                    'Native flags/producer/IRQ delivery/cache remain unverified by this original-only measurement.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS8 original IRQFLAG immediate/delayed effects; ACK releases reply, reply clears deferred PI')

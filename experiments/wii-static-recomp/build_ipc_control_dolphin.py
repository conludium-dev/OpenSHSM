"""Reuse the private pending-IPC oracle to measure original control-store semantics."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_ipc_pending_dolphin.py'
source = parent.read_text()


def replace(old, new):
    global source
    assert source.count(old) == 1, old
    source = source.replace(old, new)


source = source.replace('dolphin-ipc-pending', 'dolphin-ipc-control')
source = source.replace('run_ipc_pending_dolphin.ps1', 'run_ipc_control_dolphin.ps1')
replace('0x802175d4, 0xcd000034', '0x80241c38, 0xcd000004')
replace("replace('0x901c0000', '0x90030034')", "replace('0x901c0000', '0x7c83012e')")
replace("'    pointer(code, 0, 0x40000000 if index & 1 else 0)'",
        "'    pointer(code, 4, (0x14 if index & 1 else 0x34) if index & 2 else (0x22 if index & 1 else 0x32))\\n    pointer(code, 0, 4)'")
replace("'value': 0x40000000 if index & 1 else 0",
        "'value': (0x14 if index & 1 else 0x34) if index & 2 else (0x22 if index & 1 else 0x32)")
replace('code.append(dform(36, 0, 30, 24))', 'code.append(dform(36, 4, 30, 24))\npointer(code, 5, 0xcc000000)')
replace('dform(32, 0, 4, 0x3000), dform(36, 0, 30, 60)', 'dform(32, 0, 5, 0x3000), dform(36, 0, 30, 60)')
replace('for sweep in range(3):', '''pointer(code, 0, 0x38)
code.append(dform(36, 0, 3, 4))
code.extend([dform(32, 0, 3, 4), dform(36, 0, 30, 96)])
for sweep in range(3):''')
exec(compile(source, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-ipc-control/generation.json')
report = json.loads(path.read_text())
report['pendingGeneratorSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['scope'] = 'Original IPCWriteReg store80241C38 unchanged; adjacent return80241C3C redirected to observer. Synthetic read-only missing-device OPEN, ACK/reply preparation, control clear and X2 write.'
report['limits'] = ['Emulator control observation, not physical Wii or retail game boot.',
                    'IRQflag remains uncleared during first delayed observation; X2 write38 occurs in measurement code.',
                    'No runtime producer/interrupt/cache/full boot acceptance.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('Generated8 original IPC control-store cases: ACK/reply, enable masks, NI0/1, X2 write')

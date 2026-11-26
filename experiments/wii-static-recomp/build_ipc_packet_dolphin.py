"""Extend retained pending-IPC fixtures with a full64-byte original reply observation."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_ipc_pending_dolphin.py'
body = builder.read_text().replace('dolphin-ipc-pending', 'dolphin-ipc-packet')
body = body.replace('run_ipc_pending_dolphin.ps1', 'run_ipc_packet_dolphin.ps1')
needle = 'for sweep in range(3):'
assert body.count(needle) == 1
body = body.replace(needle, '''for offset in range(0, 64, 4):
    code.extend([dform(32, 0, 26, offset), dform(36, 0, 30, 192 + offset)])
''' + needle)
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-ipc-packet/generation.json')
report = json.loads(path.read_text())
report['pendingGeneratorSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['replyPacketBytes'] = 64
report['scope'] += ' Full64-byte reply readback at192..255 before cleanup.'
path.write_text(json.dumps(report, indent=2) + '\n')
print('Generated8originalIPCpending cases with64-byte packet observations')

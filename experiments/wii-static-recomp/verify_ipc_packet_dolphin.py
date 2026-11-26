"""Verify original pending state and all64reply bytes in a separate retained capture."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
verifier = experiment / 'verify_ipc_pending_dolphin.py'
body = verifier.read_text().replace('dolphin-ipc-pending', 'dolphin-ipc-packet')
body = body.replace('run_ipc_pending_dolphin.ps1', 'run_ipc_packet_dolphin.ps1')
body = body.replace('build_ipc_pending_dolphin.py', 'build_ipc_packet_dolphin.py')
exec(compile(body, str(verifier), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/dolphin-ipc-packet')
generation = json.loads((output / 'generation.json').read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert generation['pendingGeneratorSha256'] == sha(experiment / 'build_ipc_pending_dolphin.py') and generation['replyPacketBytes'] == 64
capture = json.loads((output / 'fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
data = base64.b64decode(capture['data'])
path = output / 'comparison.json'
report = json.loads(path.read_text())
for row in report['observations']:
    packet = data[row['index'] * 736 + 192:row['index'] * 736 + 256]
    expected = struct.pack('>5I', 8, 0xfffffffa, 1, 0x6a1000, 1) + bytes(44)
    assert packet == expected
    row['replyPacketHex'] = packet.hex()
report['result'] = 'ORIGINAL_PENDING_REPLY8_FULL64_BYTES_AND_STATE_VERIFIED'
report['pendingVerifierSha256'] = sha(verifier)
report['limits'] = ['Original64-byte readback for8synthetic read-only nonexistent-device OPEN requests; no general IOS-command/device proof.',
                    'ACK/reset causal state verified; no physical Wii timing/full boot/reset/GPIO acceptance.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS8originalreply packets/512bytes andpendingresetstates')

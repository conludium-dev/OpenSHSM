"""Verify original message write ABI/control/PI; register read is invalid, not a latch oracle."""
from pathlib import Path
import base64
import hashlib
import json
import struct

parent = Path('experiments/wii-static-recomp/verify_ipc_startup_dolphin.py')
body = parent.read_text().replace('dolphin-ipc-startup', 'dolphin-ipc-message')
body = body.replace('build_ipc_startup_dolphin.py', 'build_ipc_message_dolphin.py')
body = body.replace('run_ipc_startup_dolphin.ps1', 'run_ipc_message_dolphin.ps1')
body = body.replace('0x10000, 4, 0xcd000000, 0x38', '0x10000, 0, 0xcd000000, 0x135e0020')
body = body.replace("case['return'], 0xa032", "case['return'], 0x2032")
body = body.replace('    return fields', "    assert struct.unpack_from('>I', row, 76)[0] == 0\n    return fields")
body = body.replace('for offset in (32, 60, 64, 68):', 'for offset in (32, 40, 60, 64, 68, 76):')
body = body.replace('PASS16whole original cold control0→38 withA032/PI-mask40F8/ABI/PI unchanged/Ghidra',
    'PASS16original pointer-write/MSR2032/control38/ABI/PI/Ghidra +6mutants')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/dolphin-ipc-message')
capture = json.loads((output / 'fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
data = base64.b64decode(capture['data'])
assert all(struct.unpack_from('>I', data, index * 736 + 76)[0] == 0 for index in range(16))
report = json.loads((output / 'comparison.json').read_text())
report['result'] = 'ORIGINAL_IPC_MESSAGE16_WRITE_ABI_CONTROL_PI_INVALID_READ_ZERO'
report['invalidRegisterReads'] = [0] * 16
report['parentVerifierSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
assert generation['messageParentSha256'] == hashlib.sha256(Path('experiments/wii-static-recomp/build_ipc_startup_dolphin.py').read_bytes()).hexdigest()
report['limits'] = ['Original whole IPCWriteReg, prepared control38/message0/MSR2032/mask40F8.',
    'Message register is write-only in Dolphin; zero invalid read does not prove internal latch value.',
    'No request bit set, IOS open/ACK/reply/interrupt or physical console proof.']
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS16original message-write ABI/control/PI; invalid register reads zero, not internal latch proof')

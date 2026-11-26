"""Measure original message-register pointer write without sending an IOS request."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_ipc_startup_dolphin.py')
body = parent.read_text().replace('dolphin-ipc-startup', 'dolphin-ipc-message')
body = body.replace('run_ipc_startup_dolphin.ps1', 'run_ipc_message_dolphin.ps1')
marker = '    pointer(code, 11, 0xcd000004)'
assert body.count(marker) == 1
prep = '''    pointer(code, 3, 1)
    pointer(code, 4, 0x38)
    code.append(branch(base + len(code) * 4, 0x80241c30, True))
    pointer(code, 3, 0)
    pointer(code, 4, 0)
    code.append(branch(base + len(code) * 4, 0x80241c30, True))
'''
body = body.replace(marker, prep + marker.replace('0xcd000004', '0xcd000000'))
body = body.replace('    pointer(code, 0, 0xa032)', '    pointer(code, 0, 0x2032)')
marker = '    pointer(code, 3, 1)\n    pointer(code, 4, 0x38)\n    call ='
assert body.count(marker) == 1
body = body.replace(marker, marker.replace('3, 1', '3, 0').replace('4, 0x38', '4, 0x135e0020'))
body = body.replace('(0xcc003004, 72)]', '(0xcc003004, 72), (0xcd000000, 76)]')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-ipc-message/generation.json')
report = json.loads(path.read_text())
report['messageParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Original whole IPCWriteReg unpatched; control38/message0/MSR2032/mask40F8 lab preparation.',
    'PPC message register invalid read is captured separately; no internal latch, IOS request/reply or physical Wii proof.']
path.write_text(json.dumps(report, indent=2) + '\n')

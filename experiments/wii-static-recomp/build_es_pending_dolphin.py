"""Run original ESP_InitLib after FS OPEN while STM remains pending."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_fs_pending_dolphin.py')
body = parent.read_text().replace('dolphin-fs-pending', 'dolphin-es-pending').replace('run_fs_pending_dolphin.ps1', 'run_es_pending_dolphin.ps1')
body = body.replace('if index < 10 else', 'if index == 3 else')
body = body.replace("else b'/dev/openshsm_missing", "else b'/dev/es\\\\0' if index == 4 else b'/dev/openshsm_missing")
body = body.replace("'fsPath': '/dev/fs' if index == 3 else '/dev/openshsm_missing'", "'fsPath': '/dev/fs' if index == 3 else '/dev/es' if index == 4 else '/dev/openshsm_missing'")
body = body.replace('branch(fs_call, 0x80242550, True)', 'branch(fs_call, 0x80249790 if index == 4 else 0x80242550, True)')
body = body.replace('pointer(code, 11, 0xd35e1000)', 'pointer(code, 11, 0xc0528cf0 if index == 4 else 0xd35e1000)')
marker = "'''\nassert body.count(marker) == 1\nbody = body.replace(marker, addition + marker)"
position = body.rfind(marker)
assert position >= 0
snapshot = '''        pointer(code, 11, 0x80528ce8)
        code.extend([dform(32, 0, 11, 0), dform(36, 0, 30, 640)])
'''
body = body[:position] + body[position:].replace(marker, "'''\naddition += " + repr(snapshot) + '\n' + marker[4:], 1)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-es-pending/generation.json')
report = json.loads(path.read_text())
report['esParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Two original STM send exchanges, original async registration, one whole IOS_Open FS, one whole ESP_InitLib, eleven missing-device OPEN controls.',
    'Original /dev/es SDA path and SDK FD store; prepared thread/heap/vector/stack/other paths, not retail or physical Wii startup.',
    'No ES IOCTL/IOCTLV/certificates/title/ticket operations, FS file operations, power/network or pending callback completion.']
path.write_text(json.dumps(report, indent=2) + '\n')

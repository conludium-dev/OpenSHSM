"""Run whole original ESP_GetTitleId with guarded caller and temporary buffers."""
from pathlib import Path
import ast
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_es_pending_dolphin.py')
body = parent.read_text().replace('dolphin-es-pending', 'dolphin-es-title').replace('run_es_pending_dolphin.ps1', 'run_es_title_dolphin.ps1')
marker = "exec(compile(body, str(parent), 'exec'), {'__file__': __file__})"
prep = '''            if index >= 5:
                pointer(code, 11, 0x80500000)
                pointer(code, 0, 0xa5a5a5a5)
                for offset in range(0, 32, 4):
                    code.append(dform(36, 0, 11, offset))
                pointer(code, 11, 0x8053fee0)
                pointer(code, 0, 0xb6b6b6b6)
                for offset in range(0, 32, 4):
                    code.append(dform(36, 0, 11, offset))
                pointer(code, 3, 0x80500000)
'''
capture = '''        if index >= 5:
            pointer(code, 11, 0x80500000)
            for offset in range(0, 32, 4):
                code.extend([dform(32, 0, 11, offset), dform(36, 0, 30, 608 + offset)])
            for slot, address in [(656, 0x8053fee0), (664, 0xc053fee0), (672, 0x8053ffb0), (680, 0xc053ffb0)]:
                pointer(code, 11, address)
                for offset in (0, 4):
                    code.extend([dform(32, 0, 11, offset), dform(36, 0, 30, slot + offset)])
'''
extra = "body = body.replace('            fs_call = base + len(code) * 4', " + repr(prep) + " + '            fs_call = base + len(code) * 4')\n"
extra += "body = body.replace('0x80249790 if index == 4 else 0x80242550', '0x80249c40 if index >= 5 else 0x80249790 if index == 4 else 0x80242550')\n"
extra += "body = body.replace('0xc0528cf0 if index == 4 else 0xd35e1000', '0xc0500000 if index >= 5 else 0xc0528cf0 if index == 4 else 0xd35e1000')\n"
snapshot = next(node for node in ast.parse(body).body if isinstance(node, ast.Assign) and
    any(isinstance(target, ast.Name) and target.id == 'snapshot' for target in node.targets))
literal = ast.get_source_segment(body, snapshot.value)
assert body.count(literal) == 1
body = body.replace(literal, repr(ast.literal_eval(snapshot.value) + capture))
assert body.count(marker) == 1
body = body.replace(marker, extra + marker)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-es-title/generation.json')
report = json.loads(path.read_text())
report['titleParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
for case in report['records']:
    if case['index'] >= 5:
        case['kind'] = 'ESP_GetTitleId'
        case['callerOutput'] = 0x80500000
        case['temporaryOutput'] = 0x8053fee0
        case['vector'] = 0x8053ffb0
report['limits'] = ['Original whole ESP_GetTitleId eleven calls after STM pending/FS/ES; caller buffer A5 and temporary stack output B6 fixtures.',
    'Standalone DOL Dolphin IOS context, NOT the retail disc title context; observed title ID or failure must not be projected onto the supported game.',
    'No invented title value, IOCTL reply, credentials/tickets/certificates, filesystem writes, network, host power or callback completion.']
path.write_text(json.dumps(report, indent=2) + '\n')

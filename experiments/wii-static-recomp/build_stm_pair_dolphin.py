"""Original consecutive immediate/eventhook OPENs reuse heap and retained IPC reply state."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_stm_send_dolphin.py')
body = parent.read_text().replace('dolphin-stm-send', 'dolphin-stm-pair').replace('run_stm_send_dolphin.ps1', 'run_stm_pair_dolphin.ps1')
extra = '''body = body.replace('physical = 0x135e0020 + index * 64', 'physical = 0x135e0020')
body = body.replace('path_address = 0x4398f0 if index < 8 else 0x6a1000', 'path_address = 0x4398f0 if not index % 2 else 0x439904')
start = body.index('    if index >= 8:')
end = body.index('    pointer(code, 0, path_address)', start)
body = body[:start] + body[end:]
body = body.replace("'/dev/stm/immediate' if index < 8 else '/dev/openshsm_missing'", "'/dev/stm/immediate' if not index % 2 else '/dev/stm/eventhook'")
start = body.index('    pointer(code, 0, 0x40f8)')
end = body.index('    physical = ', start)
block = body[start:end]
body = body[:start] + '    if index == 0:\\n' + ''.join('    ' + line + '\\n' for line in block.splitlines()) + body[end:]
start = body.index('    pointer(code, 11, 0x804b2b40)')
end = body.index('    pointer(code, 3, 0)\\n    pointer(code, 4, 64)', start)
block = body[start:end]
body = body[:start] + '    if index == 0:\\n' + ''.join('    ' + line + '\\n' for line in block.splitlines()) + body[end:]
marker = '    pointer(code, 3, physical | 0x80000000)'
assert body.count(marker) == 1
body = body.replace(marker, '    code.extend([dform(32, 0, 24, 8), dform(36, 0, 30, 384), dform(32, 0, 24, 0), dform(36, 0, 30, 388), dform(32, 0, 24, 0x30), dform(36, 0, 30, 392)])\\n' + marker)
'''
marker = 'marker = "exec(compile(body, str(parent), \'exec\'), namespace)"'
assert body.count(marker) == 1
body = body.replace(marker, 'transform += ' + repr(extra) + '\n' + marker, 1)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-stm-pair/generation.json')
report = json.loads(path.read_text())
report['pairParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Original consecutive immediate/eventhook mode0 OPENs, single initialized thread/heap/queue/IPC setup; original allocation/free reused, no hardware reset between exchanges.',
    'PPC caller argument/stack/result-record fixture; no original code patches or direct handler calls.',
    'Isolated Dolphin IOS profile on own Wii US0, not retail/physical-Wii/full startup or callback/IOCTL proof.']
path.write_text(json.dumps(report, indent=2) + '\n')

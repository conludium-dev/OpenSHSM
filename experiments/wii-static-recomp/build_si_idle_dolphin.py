"""Measure the original SIInit idle loop and control acknowledgement."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_template_copy_dolphin.py'
body = builder.read_text().replace('dolphin-template-copy', 'dolphin-si-idle').replace('run_template_copy_dolphin.ps1', 'run_si_idle_dolphin.ps1')
body = body.replace('store, target, template, length, memcpy = 0x802119a8, 0x80211c08', 'store, target, template, length, memcpy = 0x8020fc94, 0xcd006434')
body = body.replace('0x901c0000', '0x3c60cd00')
marker = '    pointer(code, 28, target)'
assert body.count(marker) == 1
body = body.replace(marker, marker + '''
    pointer(code, 5, 0xcc003000)
    code.extend([dform(32, 6, 5, 0), dform(36, 6, 30, 36)])
''')
start = body.index('observer = base + len(code) * 4')
end = body.index('while len(code) % 8:', start)
body = body[:start] + '''observer = base + len(code) * 4
code.append(dform(36, 0, 30, 28))
pointer(code, 5, 0xcd006434)
code.extend([dform(32, 0, 5, 0), dform(36, 0, 30, 32)])
pointer(code, 5, 0xcc003000)
code.extend([dform(32, 0, 5, 0), dform(36, 0, 30, 40)])
pointer(code, 0, 0xc001cafe)
code.append(dform(36, 0, 30, 16))
code.extend([spr(31, 9, True), 0x4e800420])
read_observer = base + len(code) * 4
code.append(dform(36, 0, 30, 24))
code.append(0x540007ff)
code.append(branch(base + len(code) * 4, 0x8020fca0))
''' + body[end:]
body = body.replace('store_offset + 4', 'store_offset + 32').replace('store + 4', 'store + 32')
marker = 'header[56] = base'
body = body.replace(marker, "struct.pack_into('>I', image, store_offset + 8, branch(store + 8, read_observer))\n" + marker)
namespace = {'__file__': __file__}
exec(compile(body, str(builder), 'exec'), namespace)
path = Path('work/private-game/static-recomp/dolphin-si-idle/generation.json')
report = json.loads(path.read_text())
report['baseGeneratorSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['readObserverAddress'] = namespace['read_observer']
report['scope'] = 'Original SIInit8020FC94..FCB0 loop/read/write; FC9C raw-read observer replays exact clrlwi., FCB4 exit observer only. Unseeded SI/PI state, prepared MSR/HID0,16repetitions.'
report['limits'] = ['Idle-loop/acknowledgement fragment only, not whole SIInit, active transfers, device polling, physical Wii or game image.', 'No forced SI busy/TCINT events; persistent Dolphin loader hardware profile.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('Generated16 original SI idle/acknowledgement fragments; no hardware state seed')

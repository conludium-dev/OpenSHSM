"""Run whole original SISetXY with disclosed polling mirror fixtures."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_template_copy_dolphin.py'
body = builder.read_text().replace('dolphin-template-copy', 'dolphin-si-xy').replace('run_template_copy_dolphin.ps1', 'run_si_xy_dolphin.ps1')
body = body.replace('store, target, template, length, memcpy = 0x802119a8, 0x80211c08', 'store, target, template, length, memcpy = 0x8020feb0, 0xcd006430')
body = body.replace('0x901c0000', '0x9421fff0')
marker = '    pointer(code, 28, target)'
assert body.count(marker) == 1
body = body.replace(marker, marker + '''
    pointer(code, 2, 0x805335e0)
    pointer(code, 13, 0x8052e720)
    pointer(code, 3, 492 if index < 8 else 28)
    pointer(code, 4, 2 if index < 8 else 19)
    pointer(code, 5, 0x8042b6f4)
    pointer(code, 6, (index % 8) * 0x04000001)
    code.append(dform(36, 6, 5, 0))
''')
start = body.index('observer = base + len(code) * 4')
end = body.index('while len(code) % 8:', start)
body = body[:start] + '''observer = base + len(code) * 4
code.append(dform(36, 3, 30, 24))
pointer(code, 5, 0xcd006430)
code.extend([dform(32, 0, 5, 0), dform(36, 0, 30, 28)])
pointer(code, 5, 0x8042b6f4)
code.extend([dform(32, 0, 5, 0), dform(36, 0, 30, 32)])
code.extend([0x7c0000a6, dform(36, 0, 30, 36)])
pointer(code, 0, 0xc001cafe)
code.append(dform(36, 0, 30, 16))
code.extend([spr(31, 9, True), 0x4e800420])
''' + body[end:]
body = body.replace('store_offset + 4', 'store_offset + 88').replace('store + 4', 'store + 88')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-si-xy/generation.json')
report = json.loads(path.read_text())
report['baseGeneratorSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['records'] = [{'index': i, 'x': 492 if i < 8 else 28, 'y': 2 if i < 8 else 19, 'mirrorBefore': (i % 8) * 0x04000001} for i in range(16)]
report['scope'] = 'Whole original SISetXY8020FEB0..FF08 with OSDisable/RestoreInterrupts; BLR observerFF08 only. Prepared r2/r13/MSR/HID0 and Si+4 mirror, persistent hardware.'
report['limits'] = ['No whole SI initialization, device transfers/input polling, physical Wii or game frame.', 'Prepared mirror/channel flags are fixtures, not evidence of their producers.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('Generated16 whole original SISetXY calls; no original instructions changed before final BLR')

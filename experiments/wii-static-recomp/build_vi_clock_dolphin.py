"""Measure the original VI-clock sampling calculation; no SI writes executed."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_template_copy_dolphin.py'
body = builder.read_text().replace('dolphin-template-copy', 'dolphin-vi-clock').replace('run_template_copy_dolphin.ps1', 'run_vi_clock_dolphin.ps1')
body = body.replace('store, target, template, length, memcpy = 0x802119a8, 0x80211c08', 'store, target, template, length, memcpy = 0x80210618, 0xcc00206c')
body = body.replace('0x901c0000', '0x3c60cc00')
marker = '    pointer(code, 28, target)'
assert body.count(marker) == 1
body = body.replace(marker, marker + '\n    pointer(code, 29, index % 8)\n    pointer(code, 5, 0x8042b718 + (0x30 if index >= 8 else 0))')
start = body.index('observer = base + len(code) * 4')
end = body.index('while len(code) % 8:', start)
body = body[:start] + '''observer = base + len(code) * 4
for register, offset in [(3, 28), (4, 32), (5, 36), (0, 40)]:
    code.append(dform(36, register, 30, offset))
pointer(code, 0, 0xc001cafe)
code.append(dform(36, 0, 30, 16))
code.extend([spr(31, 9, True), 0x4e800420])
read_observer = base + len(code) * 4
code.append(dform(36, 4, 30, 24))
code.append(0x7c650214)
code.append(branch(base + len(code) * 4, 0x80210628))
''' + body[end:]
body = body.replace('store_offset + 4', 'store_offset + 36').replace('store + 4', 'store + 36')
marker = 'header[56] = base'
body = body.replace(marker, "struct.pack_into('>I', image, store_offset + 12, branch(store + 12, read_observer))\n" + marker)
namespace = {'__file__': __file__}
exec(compile(body, str(builder), 'exec'), namespace)
path = Path('work/private-game/static-recomp/dolphin-vi-clock/generation.json')
report = json.loads(path.read_text())
report['baseGeneratorSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['readObserverAddress'] = namespace['read_observer']
report['records'] = [{'index': index, 'rate': index % 8, 'tableAddress': 0x8042b718 + (0x30 if index >= 8 else 0)} for index in range(16)]
report['scope'] = 'Original SISetSamplingRate calculation80210618..10638; observer10624 replays add, exit1063C replaces SISetXY call. Synthetic rate/table/MSR/HID fixtures.'
report['limits'] = ['No full SISetSamplingRate, SISetXY, controller polling, retail startup, physical Wii or visual acceptance.', 'Clock value is an unseeded Dolphin loader observation, not a universal Wii register default.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('Generated16 original VI clock/calculation cases; raw-read observer and pre-SI exit')

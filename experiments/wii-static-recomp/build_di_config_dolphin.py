"""Measure the original DI configuration getter used by EXISync."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_template_copy_dolphin.py'
body = builder.read_text().replace('dolphin-template-copy', 'dolphin-di-config').replace('run_template_copy_dolphin.ps1', 'run_di_config_dolphin.ps1')
body = body.replace('store, target, template, length, memcpy = 0x802119a8, 0x80211c08', 'store, target, template, length, memcpy = 0x80211d00, 0xcd006024')
body = body.replace('0x901c0000', '0x3c60cd00')
start = body.index('observer = base + len(code) * 4')
end = body.index('while len(code) % 8:', start)
body = body[:start] + '''observer = base + len(code) * 4
code.extend([dform(36, 3, 30, 24), dform(36, 0, 30, 28)])
pointer(code, 0, 0xc001cafe)
code.append(dform(36, 0, 30, 16))
code.extend([spr(31, 9, True), 0x4e800420])
''' + body[end:]
body = body.replace('store_offset + 4', 'store_offset + 12').replace('store + 4', 'store + 12')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-di-config/generation.json')
report = json.loads(path.read_text())
report['baseGeneratorSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['scope'] = 'Original3instructions80211D00..D08 unchanged; BLR observer80211D0C only. SyntheticGPR/MSR/HID0;16repeated reads.'
report['limits'] = ['DI configuration getter only, not disc commands/DMA or physical Wii.']
path.write_text(json.dumps(report, indent=2) + '\n')

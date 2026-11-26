"""Reuse original template-copy observations for the exact second NOP store."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_template_modes_dolphin.py'
body = builder.read_text().replace('dolphin-template-modes', 'dolphin-nop-copy')
body = body.replace('run_template_modes_dolphin.ps1', 'run_nop_copy_dolphin.ps1')
needle = "exec(compile(body, str(builder), 'exec'), {'__file__': __file__})"
replacement = '''body = body.replace('store, target, template, length, memcpy = 0x802119a8, 0x80211c08', 'store, target, template, length, memcpy = 0x80211a30, 0x80211bf8')
body = body.replace('== 0x901c0000', '== 0x92e40000').replace("'storeOpcode': 0x901c0000", "'storeOpcode': 0x92e40000")
body = body.replace('pointer(code, 28, target)', 'pointer(code, 4, target)')
body = body.replace('pointer(code, 0, 0x38600000 | (index & 15))', 'pointer(code, 23, 0x60000000)')
body = body.replace("'value': 0x38600000 | (index & 15)", "'value': 0x60000000")
body = body.replace('code.append(dform(36, 0, 30, 24))', 'code.append(dform(36, 23, 30, 24))')
''' + needle
assert body.count(needle) == 1
body = body.replace(needle, replacement)
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-nop-copy/generation.json')
report = json.loads(path.read_text())
report['modeGeneratorSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['scope'] = 'Original80211A30 NOP store and memcpy/NI setter unchanged; adjacent observer branch and synthetic cache/register/destination fixtures.'
path.write_text(json.dumps(report, indent=2) + '\n')
print('Generated32original NOP-store/template-copy observations atNI0/NI1')

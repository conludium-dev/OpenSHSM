"""Measure real SDK ES close, repeated close, invalid raw close and FD reuse."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_es_datadir_dolphin.py')
body = parent.read_text().replace('dolphin-es-datadir', 'dolphin-es-close').replace(
    'run_es_datadir_disc_dolphin.ps1', 'run_es_close_disc_dolphin.ps1')
body = body.replace("    if name == 'prep':", "    if name == 'prep':\n        value = value.replace('if index >= 5:', 'if index in (5, 6):')")
body = body.replace('            if index >= 6:', '            if index == 6:')
body = body.replace('                pointer(code, 5, 0x80500000)\n',
    '                pointer(code, 5, 0x80500000)\n            if index in (9, 12):\n                pointer(code, 3, 3)\n')
marker = "body = body.replace('0x80249c40 if index >= 5 else', '0x80249ba0 if index >= 6 else 0x80249c40 if index == 5 else')"
assert body.count(marker) == 1
replacement = """body = body.replace('0x80249c40 if index >= 5 else',
    '0x802497f0 if index in (7, 8, 11, 13, 15) else 0x80242740 if index in (9, 12) else 0x80249790 if index in (10, 14) else 0x80249ba0 if index == 6 else 0x80249c40 if index == 5 else')"""
body = body.replace(marker, replacement)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-es-close/generation.json')
report = json.loads(path.read_text())
report['closeParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
for case in report['records']:
    index = case['index']
    if index >= 7:
        case['kind'] = 'ESP_CloseLib' if index in (7, 8, 11, 13, 15) else 'IOS_Close_invalid_fd3' if index in (9, 12) else 'ESP_InitLib_reopen'
report['limits'] = ['Original STM pending/FS/ES/title/GetDataDir then whole SDK ES closes, already-closed SDK calls, invalid raw FD3 closes and reopen/reuse.',
    'No forced FD state or service results. Title comes from original response; private own-disc custom-entry/thread/heap context.',
    'No original assets published, host savedata writes, STM callback completion, power/network or physical/full-retail proof.']
path.write_text(json.dumps(report, indent=2) + '\n')

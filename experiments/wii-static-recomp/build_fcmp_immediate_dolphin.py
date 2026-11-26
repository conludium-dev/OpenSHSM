"""Measure FPSCR immediately at the adjacent observer, retaining the earlier discrepancy capture."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_fcmp_dolphin.py')
body = parent.read_text().replace('dolphin-fcmp','dolphin-fcmp-immediate').replace(
    'run_fcmp_dolphin.ps1','run_fcmp_immediate_dolphin.ps1')
marker = 'observer = []'
assert body.count(marker) == 1
body = body.replace(marker,"code.extend([(63 << 26) | (30 << 21) | (583 << 1),dform(54,30,29,712)])\n" + marker)
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
path = Path('work/private-game/static-recomp/dolphin-fcmp-immediate/generation.json')
report = json.loads(path.read_text())
report['parentGeneratorSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'].append('Immediate mffs/stfd captured at712 before shared observer; no original compare patch.')
path.write_text(json.dumps(report,indent=2) + '\n')

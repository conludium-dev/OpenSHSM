"""Repeat SC whole-call fixture with read-only SDA-register diagnostics."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_sysconf_dolphin.py')
body = parent.read_text().replace('dolphin-sysconf', 'dolphin-sysconf-register').replace(
    'run_sysconf_disc_dolphin.ps1', 'run_sysconf_register_disc_dolphin.ps1')
body = body.replace('        if index >= 8:', '        if index >= 8:\n            code.append(dform(36, 13, 30, 644))\n            code.extend([dform(34, 0, 13, -0x3718), dform(36, 0, 30, 652)])', 1)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-sysconf-register/generation.json')
report = json.loads(path.read_text())
report['registerParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'].append('Read-only r13 and relative SC status diagnosis; no corrected SDA, source global flags or file result supplied.')
path.write_text(json.dumps(report, indent=2) + '\n')

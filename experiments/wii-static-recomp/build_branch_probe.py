"""Extend the existing CPU/cache observer to the next taken boot backedge."""
from pathlib import Path
import hashlib
import json

base = Path('experiments/wii-static-recomp/build_l2_probe.py')
body = base.read_text().replace('dolphin-l2-probe', 'dolphin-branch-probe').replace('run_l2_probe.ps1', 'run_branch_probe.ps1')
body = body.replace('endpoint = 0x80213534', 'endpoint = 0x8000656c')
body = body.replace('assert opcode == 0x4082fff8', 'assert opcode == 0x4bffffc4')
exec(compile(body, str(base), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-branch-probe/generation.json')
report = json.loads(path.read_text())
report['l2GeneratorSha256'] = hashlib.sha256(base.read_bytes()).hexdigest()
report['scope'] = 'Private observer before original taken __init_data backedge8000656C; not retail boot or scheduler acceptance.'
path.write_text(json.dumps(report, indent=2) + '\n')

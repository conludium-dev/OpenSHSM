"""Reuse the existing observer before the first quarantined OS timebase read."""
from pathlib import Path
import hashlib
import json

base = Path('experiments/wii-static-recomp/build_branch_probe.py')
body = base.read_text().replace('dolphin-branch-probe', 'dolphin-poll-probe').replace('run_branch_probe.ps1', 'run_poll_probe.ps1')
body = body.replace('endpoint = 0x8000656c', 'endpoint = 0x8021c000')
body = body.replace('assert opcode == 0x4bffffc4', 'assert opcode == 0x7c6d42e6')
exec(compile(body, str(base), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-poll-probe/generation.json')
report = json.loads(path.read_text())
report['branchGeneratorSha256'] = hashlib.sha256(base.read_bytes()).hexdigest()
report['scope'] = 'Private observer before original timebase reader8021C000; no timer/scheduler or retail boot acceptance.'
path.write_text(json.dumps(report, indent=2) + '\n')

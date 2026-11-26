"""Reuse whole-module compile/link workflow for the generic subfic correction."""
from pathlib import Path
import hashlib
import json

builder = Path('experiments/wii-static-recomp/build_branch.py')
body = builder.read_text().replace('from branch_lowering import lower', 'from carry_lowering import lower')
body = body.replace("base = Path('work/private-game/static-recomp/mass-l2')", "base = Path('work/private-game/static-recomp/mass-branch')")
body = body.replace("output = Path('work/private-game/static-recomp/mass-branch')", "output = Path('work/private-game/static-recomp/mass-carry')")
body = body.replace("str(experiment / 'l2_adapter.h')", "str(experiment / 'carry_adapter.h')")
body = body.replace("sha(experiment / 'branch_lowering.py')", "sha(experiment / 'carry_lowering.py')")
body = body.replace("wrapper = base / 'boot-wrapper.cpp'", "wrapper = Path('work/private-game/static-recomp/mass-poll/boot-wrapper.cpp')")
body = body.replace("policy = base / 'boot-quarantine.tsv'", "policy = Path('work/private-game/static-recomp/mass-l2/boot-quarantine.tsv')")
body = body.replace('Generic backedge sites:', 'Generic subfic sites:')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-carry/lowering.json')
report = json.loads(path.read_text())
report['baseBuilderSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['adapterSha256'] = hashlib.sha256(Path('experiments/wii-static-recomp/carry_adapter.h').read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')
boot_path = path.parent / 'boot.json'
boot = json.loads(boot_path.read_text())
boot['loweringSha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
boot['result'] = 'SUBFIC_BOOT_ENDPOINT_REQUIRES_ORACLE'
boot_path.write_text(json.dumps(boot, indent=2) + '\n')

"""Retain the GetID fixture but leave all original instruction bytes intact."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_exi_getid_dolphin.py'
body = builder.read_text().replace('dolphin-exi-getid', 'dolphin-exi-getid-unobserved')
body = body.replace('run_exi_getid_dolphin.ps1', 'run_exi_getid_unobserved_dolphin.ps1')
before = "    struct.pack_into('>I', image, patch['offset'], branch(patch['address'], patch['trampoline']))"
assert body.count(before) == 1
body = body.replace(before, '    pass')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-exi-getid-unobserved/generation.json')
report = json.loads(path.read_text())
report['patches'] = []
report['baseGeneratorSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['scope'] = 'Whole original EXIGetID and dependencies unchanged; wrapper before/after snapshots only.'
report['limits'] = ['Same prepared fixtures/None serial-port configuration as observed call; no internal phase capture.',
                    'Repeated calls retain other hardware/mask state; no retail startup or physical Wii proof.']
path.write_text(json.dumps(report, indent=2) + '\n')

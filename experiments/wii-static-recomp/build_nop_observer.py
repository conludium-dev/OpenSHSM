"""Reuse the diagnostic module builder for the second blocked store."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
base = Path('work/private-game/static-recomp/mass-template-patch')
output = Path('work/private-game/static-recomp/mass-nop-observer')
output.mkdir(exist_ok=True)
for filename in ('loader-bat-seed.h', 'fp64-template-probe.h', 'mutable-template-probe.h'):
    (output / filename).write_bytes((base / filename).read_bytes())
builder = experiment / 'build_code_write_observer.py'
body = builder.read_text().replace('mass-code-write-observer', 'mass-nop-observer').replace('mass-ni-guard', 'mass-template-patch')
body = body.replace('code_write_lowering', 'nop_observer_lowering').replace("'code_write_observer.h'", "'template_patch.h'")
body = body.replace("body = body.replace(\"str(wrapper), str(experiment / 'processor_adapter.cpp')\"", "body = body.replace(\"policy = base / 'boot-quarantine.tsv'\", \"policy = Path('work/private-game/static-recomp/mass-ni-guard/boot-quarantine.tsv')\")\nbody = body.replace(\"str(wrapper), str(experiment / 'processor_adapter.cpp')\"")
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
path = output / 'lowering.json'
report = json.loads(path.read_text())
report['observerBuilderSha256'] = sha(builder)
report['privateHeaderSha256'] = {name: sha(output / name) for name in ('loader-bat-seed.h', 'fp64-template-probe.h', 'mutable-template-probe.h')}
path.write_text(json.dumps(report, indent=2) + '\n')
boot_path = output / 'boot.json'
boot = json.loads(boot_path.read_text())
boot['loweringSha256'] = sha(path)
boot_path.write_text(json.dumps(boot, indent=2) + '\n')

"""Link a table-write diagnostic on the current module without new write permissions."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_nop_observer.py'
body = builder.read_text().replace('mass-template-patch', 'mass-template-nop').replace('mass-nop-observer', 'mass-table-observer')
body = body.replace('nop_observer_lowering', 'table_write_lowering').replace("'template_patch.h'", "'table_write_observer.h'")
needle = "exec(compile(body, str(builder), 'exec'), {'__file__': __file__})"
assert body.count(needle) == 1
body = body.replace(needle, "body = body.replace(\"assert report['sites'] == 1\", \"assert report['sites'] == 17\")\n" + needle)
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-table-observer')
path = output / 'lowering.json'
report = json.loads(path.read_text())
report['nopBuilderSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')
boot_path = output / 'boot.json'
boot = json.loads(boot_path.read_text())
boot['loweringSha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
boot_path.write_text(json.dumps(boot, indent=2) + '\n')

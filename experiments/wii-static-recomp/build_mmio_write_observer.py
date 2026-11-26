"""Link exact memory-write diagnostics on the verified reset module."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_nop_observer.py'
body = builder.read_text().replace('mass-template-patch', 'mass-template-reset').replace('mass-nop-observer', 'mass-mmio-observer')
body = body.replace('nop_observer_lowering', 'mmio_write_lowering').replace("'template_patch.h'", "'mmio_write_observer.h'")
needle = "exec(compile(body, str(builder), 'exec'), {'__file__': __file__})"
assert body.count(needle) == 1
body = body.replace(needle, "body = body.replace(\"assert report['sites'] == 1\", \"assert report['sites'] == 10\")\n" + needle)
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-mmio-observer')
path = output / 'lowering.json'
report = json.loads(path.read_text())
report['nopBuilderSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['result'] = 'MEMORY_WRITE_OBSERVER_COMPILED_NO_NEW_PERMISSIONS'
path.write_text(json.dumps(report, indent=2) + '\n')
boot_path = output / 'boot.json'
boot = json.loads(boot_path.read_text())
boot['loweringSha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
boot['result'] = 'EXACT_MEMORY_WRITE_DIAGNOSTIC_ENDPOINT_UNVERIFIED'
boot_path.write_text(json.dumps(boot, indent=2) + '\n')

"""Extend only the reset store in a separate module, retaining all other guards."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_nop_observer.py'
body = builder.read_text().replace('mass-template-patch', 'mass-table-observer').replace('mass-nop-observer', 'mass-template-reset')
body = body.replace('nop_observer_lowering', 'template_reset_lowering').replace("'template_patch.h'", "'template_reset.h'")
needle = "builder = experiment / 'build_code_write_observer.py'"
assert body.count(needle) == 1
body = body.replace(needle, '''probe = (base / 'mutable-template-probe.h').read_text().replace('#include "template_nop.h"', '#include "template_reset.h"')
probe = probe.replace('        experiment_template_nop(context, 0x80211bf8, 0x60000000, 0x80211a30);', '        experiment_template_nop(context, 0x80211bf8, 0x60000000, 0x80211a30);\\n        experiment_template_reset(context, 0x80211c08, 0x38600000, 0x80211b0c);')
(output / 'mutable-template-probe.h').write_text(probe)
''' + needle)
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-template-reset')
path = output / 'lowering.json'
report = json.loads(path.read_text())
report['nopObserverBuilderSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['result'] = 'SCOPED_RESET_STORE_COMPILED_EXECUTION_ENDPOINT_UNVERIFIED'
path.write_text(json.dumps(report, indent=2) + '\n')
boot_path = output / 'boot.json'
boot = json.loads(boot_path.read_text())
boot['loweringSha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
boot['result'] = 'SCOPED_RESET_STORE_NEXT_BOOT_ENDPOINT_UNVERIFIED'
boot_path.write_text(json.dumps(boot, indent=2) + '\n')

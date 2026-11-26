"""Extend the same template patch module with the measured idempotent NOP store."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_nop_observer.py'
body = builder.read_text().replace('mass-nop-observer', 'mass-template-nop')
body = body.replace('nop_observer_lowering', 'template_nop_lowering').replace("'template_patch.h'", "'template_nop.h'")
needle = "builder = experiment / 'build_code_write_observer.py'"
body = body.replace(needle, '''probe = (base / 'mutable-template-probe.h').read_text().replace('#include "template_patch.h"', '#include "template_nop.h"')
probe = probe.replace('        experiment_template_patch(context, 0x80211c08, value, 0x802119a8);', '        experiment_template_patch(context, 0x80211c08, value, 0x802119a8);\\n        experiment_template_nop(context, 0x80211bf8, 0x60000000, 0x80211a30);')
(output / 'mutable-template-probe.h').write_text(probe)
''' + needle)
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-template-nop')
path = output / 'lowering.json'
report = json.loads(path.read_text())
report['nopObserverBuilderSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')
boot_path = output / 'boot.json'
boot = json.loads(boot_path.read_text())
boot['loweringSha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
boot['result'] = 'MEASURED_NOP_STORE_COMPILED_NEXT_BOOT_ENDPOINT_UNVERIFIED'
boot_path.write_text(json.dumps(boot, indent=2) + '\n')

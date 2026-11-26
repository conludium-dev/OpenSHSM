"""Reuse exact-object SI regression with the two-OPEN profile disabled."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_stm_startup_si_regression.py')
body = parent.read_text().replace('mass-stm-startup-boot', 'mass-stm-eventhook-boot')
body = body.replace('NEW_BOOT_STM_OBJECTS_SI16', 'NEW_EVENTHOOK_OBJECTS_SI16')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-stm-eventhook-boot/si-regression.json')
report = json.loads(path.read_text())
report['eventhookParentVerifierSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')

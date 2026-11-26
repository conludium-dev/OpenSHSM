"""Replay SI on actual async-profile objects with all STM admission off."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_stm_startup_si_regression.py')
body = parent.read_text().replace('mass-stm-startup-boot', 'mass-stm-async-boot')
body = body.replace('NEW_BOOT_STM_OBJECTS_SI16', 'NEW_ASYNC_OBJECTS_SI16')
marker = "exec(compile(body, str(parent), 'exec'), {'__file__': __file__})"
inject = 'body = body.replace(' + repr("host.write_text('#include ") + ', ' + repr('host.write_text(\'#include "stm_async_dispatch.h"\\n#include ') + ', 1)\n'
assert body.count(marker) == 1
body = body.replace(marker, inject + marker)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-stm-async-boot/si-regression.json')
report = json.loads(path.read_text())
report['asyncParentVerifierSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')

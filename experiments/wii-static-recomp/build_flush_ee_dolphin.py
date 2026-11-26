"""Reuse original whole flush oracle, enabling EE only after original vector installation."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_flush_syscall_dolphin.py')
body = parent.read_text().replace('dolphin-flush-syscall', 'dolphin-flush-ee')
body = body.replace('run_flush_syscall_dolphin.ps1', 'run_flush_ee_dolphin.ps1')
marker = '\nfor index in range(16):'
assert body.count(marker) == 1
body = body.replace(marker, "\npointer(code, 0, 0xa032)\ncode.append((31 << 26) | (146 << 1))" + marker)
body = body.replace('Prepared MSR2032', 'Prepared MSRA032 after original installer at2032')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-flush-ee/generation.json')
report = json.loads(path.read_text())
report['eeParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')

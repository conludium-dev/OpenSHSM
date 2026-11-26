"""Run the existing unpatched UART fixture with RI enabled, preserving the old control."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_uart_unobserved_dolphin.py')
body = parent.read_text().replace('dolphin-uart-unobserved', 'dolphin-uart-ri').replace('run_uart_unobserved_dolphin.ps1', 'run_uart_ri_dolphin.ps1')
marker = "\nexec(compile(body, str(builder), 'exec'), {'__file__': __file__})"
assert body.count(marker) == 1
body = body.replace(marker, '\nbody = body.replace(line, \'body = body.replace("0x2030", "0x2032")\\n\' + line)' + marker)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-uart-ri/generation.json')
report = json.loads(path.read_text())
report['riParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['scope'] = 'Whole original unpatched EUART with MSR2032/RI; compare against retained MSR2030fixture.'
path.write_text(json.dumps(report, indent=2) + '\n')

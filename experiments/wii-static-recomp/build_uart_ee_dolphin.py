"""Measure unpatched whole EUART/EXISync with EE and RI enabled."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_uart_unobserved_dolphin.py')
body = parent.read_text()
body = body.replace('dolphin-uart-unobserved', 'dolphin-uart-ee')
body = body.replace('run_uart_unobserved_dolphin.ps1', 'run_uart_ee_dolphin.ps1')
marker = "\nexec(compile(body, str(builder), 'exec'), {'__file__': __file__})"
old = '    code.extend([dform(14, 0, 0, 0x2030), (31 << 26) | (146 << 1)])'
new = '    pointer(code, 0, 0xa032)\n    code.append((31 << 26) | (146 << 1))'
assert body.count(marker) == 1
injection = 'assert body.count(' + repr(old) + ') == 1\nbody = body.replace(' + repr(old) + ', ' + repr(new) + ')\n'
body = body.replace(marker, '\nbody = body.replace(line, ' + repr(injection) + ' + line)' + marker)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-uart-ee/generation.json')
report = json.loads(path.read_text())
report['eeParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['scope'] = 'Unpatched whole original EUART and EXISync with initial MSRA032, prepared payload/ECB/NI fixture.'
report['limits'] = ['No full retail startup, STM coexistence, physical Wii or interrupt timing proof; final snapshots only.']
path.write_text(json.dumps(report, indent=2) + '\n')

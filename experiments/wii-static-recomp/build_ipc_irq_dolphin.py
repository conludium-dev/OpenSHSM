"""Extend the existing control oracle with IRQFLAG-clear observations."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
control_builder = experiment / 'build_ipc_control_dolphin.py'
body = control_builder.read_text().replace('dolphin-ipc-control', 'dolphin-ipc-irq')
body = body.replace('run_ipc_control_dolphin.ps1', 'run_ipc_irq_dolphin.ps1')
needle = "code.extend([dform(32, 0, 3, 4), dform(36, 0, 30, 96)])\nfor sweep in range(3):"
assert body.count(needle) == 1
body = body.replace(needle, """code.extend([dform(32, 0, 3, 4), dform(36, 0, 30, 96)])
pointer(code, 0, 0x40000000)
code.append(dform(36, 0, 3, 0x30))
code.extend([dform(32, 0, 5, 0x3000), dform(36, 0, 30, 100),
             dform(32, 0, 3, 4), dform(36, 0, 30, 104),
             dform(32, 0, 3, 8), dform(36, 0, 30, 108)])
delay(code, 50000)
code.extend([dform(32, 0, 5, 0x3000), dform(36, 0, 30, 112),
             dform(32, 0, 3, 4), dform(36, 0, 30, 116),
             dform(32, 0, 3, 8), dform(36, 0, 30, 120)])
for sweep in range(3):""")
exec(compile(body, str(control_builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-ipc-irq/generation.json')
report = json.loads(path.read_text())
report['controlGeneratorSha256'] = hashlib.sha256(control_builder.read_bytes()).hexdigest()
report['scope'] += ' IRQFLAG write40000000 and immediate/delayed PI cause/control/ARM-message reads occur in measurement code before cleanup.'
path.write_text(json.dumps(report, indent=2) + '\n')
print('Generated8 original control cases with IPC IRQFLAG-clear/PI observations')

"""Leave original EUART code intact to check observer effects."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_uart_dolphin.py'
body = builder.read_text().replace('dolphin-uart', 'dolphin-uart-unobserved').replace('run_uart_dolphin.ps1', 'run_uart_unobserved_dolphin.ps1')
line = "exec(compile(body, str(builder), 'exec'), {'__file__': __file__})"
assert body.count(line) == 1
before = "    struct.pack_into('>I', image, patch['offset'], branch(patch['address'], patch['trampoline']))"
body = body.replace(line, 'body = body.replace(' + repr(before) + ', "    pass")\n' + line)
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-uart-unobserved/generation.json')
report = json.loads(path.read_text())
report['patches'] = []
report['baseUartGeneratorSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['scope'] = 'Whole original EUART code unchanged; same prepared fixtures, wrapper before/final snapshots only.'
path.write_text(json.dumps(report, indent=2) + '\n')

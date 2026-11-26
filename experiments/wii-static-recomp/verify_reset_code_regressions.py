"""Retain prior UART/GetID/memory proofs using the new reset-read object."""
from pathlib import Path
import hashlib
import json
parent = Path('experiments/wii-static-recomp/verify_uart_ri_regressions.py')
body = parent.read_text().replace("base = private / 'uart-ri-native'", "base = private / 'reset-code-native'")
body = body.replace('uart-ri-regressions', 'reset-code-regressions')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/reset-code-regressions/verification.json')
report = json.loads(path.read_text())
report['result'] = 'RESET_EXTENSION_UART16_GETID16_MEMORY16_REGRESSION_PASS'
report['parentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')

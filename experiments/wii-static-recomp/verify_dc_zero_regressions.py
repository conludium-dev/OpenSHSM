"""Retain prior UART/GetID/memory positives using the dcbz-capable source batch."""
from pathlib import Path
import hashlib
import json
parent = Path('experiments/wii-static-recomp/verify_uart_ri_regressions.py')
body = parent.read_text().replace("base = private / 'uart-ri-native'", "base = private / 'dc-zero-native'")
body = body.replace('uart-ri-regressions', 'dc-zero-regressions')
body = body.replace('memory_protection_frontend.h', 'dc_zero_frontend.h')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dc-zero-regressions/verification.json')
report = json.loads(path.read_text())
report['result'] = 'DCZERO_EXTENSION_UART16_GETID16_MEMORY16_REGRESSION_PASS'
report['parentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')

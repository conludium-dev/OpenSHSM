"""Independently decode the original EXISync span from the private dtk object."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'verify_uart_ghidra.py'
Path('work/private-game/static-recomp/exi-sync-ee/ghidra').mkdir(parents=True, exist_ok=True)
body = parent.read_text()
old = "[('fn_8020F3C0', 'auto_03_802045CC_text.o', 98, 392), ('fn_80240320', 'auto_03_802045CC_text.o', 140, 560)]"
assert body.count(old) == 1
body = body.replace(old, "[('EXISync', 'auto_03_802045CC_text.o', 159, 636)]")
body = body.replace('uart-native/ghidra', 'exi-sync-ee/ghidra')
body = body.replace('UART helper/write spans238instructions/952bytes', 'EXISync span159instructions/636bytes')
body = body.replace('ORIGINAL_UART_SPANS_GHIDRA238_INSTRUCTIONS952_BYTES_DECODED', 'ORIGINAL_EXISYNC_SPAN_GHIDRA159_INSTRUCTIONS636_BYTES_DECODED')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/exi-sync-ee/ghidra/verification.json')
report = json.loads(path.read_text())
report['parentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')

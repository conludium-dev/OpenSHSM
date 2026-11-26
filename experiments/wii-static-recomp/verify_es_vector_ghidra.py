"""Independently decode the original title-ID wrapper and ioctl-vector preparation."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'verify_uart_ghidra.py'
Path('work/private-game/static-recomp/es-vector-source/ghidra').mkdir(parents=True, exist_ok=True)
body = parent.read_text()
old = "[('fn_8020F3C0', 'auto_03_802045CC_text.o', 98, 392), ('fn_80240320', 'auto_03_802045CC_text.o', 140, 560)]"
assert body.count(old) == 1
body = body.replace(old, "[('ESP_GetTitleId', 'auto_03_802045CC_text.o', 38, 152), ('IOS_Ioctlv', 'auto_03_802045CC_text.o', 55, 220), ('fn_80242F60', 'auto_03_802045CC_text.o', 79, 316)]")
body = body.replace('uart-native/ghidra', 'es-vector-source/ghidra')
body = body.replace('UART helper/write spans238instructions/952bytes', 'ES title/vector spans172instructions/688bytes')
body = body.replace('ORIGINAL_UART_SPANS_GHIDRA238_INSTRUCTIONS952_BYTES_DECODED', 'ORIGINAL_ES_TITLE_VECTOR_SPANS172_INSTRUCTIONS688_BYTES_DECODED')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/es-vector-source/ghidra/verification.json')
report = json.loads(path.read_text())
report['parentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Original dtk object spans and independently discovered Ghidra bodies; not IOCTLV execution or original title-ID response.',
    'SDA labels in decompiler output are not trusted as runtime addresses; own DOL opcodes and native snapshots are separate evidence.',
    'Headless Ghidra, MCP unavailable; no physical Wii or retail-startup proof.']
path.write_text(json.dumps(report, indent=2) + '\n')

"""Independently decode SDK close and raw close allocation/send/free."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_es_datadir_ghidra.py')
body = parent.read_text().replace('es-datadir-source/ghidra', 'es-close-source/ghidra').replace(
    "[('ESP_GetDataDir', 'auto_03_802045CC_text.o', 38, 152)]",
    "[('ESP_CloseLib', 'auto_03_802045CC_text.o', 18, 72), ('fn_80242740', 'auto_03_802045CC_text.o', 42, 168)]")
body = body.replace('ES data-dir span38instructions/152bytes', 'ES close spans60instructions/240bytes').replace(
    'ORIGINAL_ES_DATADIR_SPAN38_INSTRUCTIONS152_BYTES_DECODED', 'ORIGINAL_ES_CLOSE_SPANS60_INSTRUCTIONS240_BYTES_DECODED')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/es-close-source/ghidra/verification.json')
report = json.loads(path.read_text())
report['closeParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Original dtk/DOL spans, independently discovered Ghidra bodies; SDK FD store, raw-close packet/send/free static evidence.',
    'Not executed IOS result/descriptor reuse, physical Wii or complete retail startup. Headless, MCP unavailable.']
path.write_text(json.dumps(report, indent=2) + '\n')

"""Independently decode the original GetDataDir wrapper, without forcing body boundaries."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'verify_es_vector_ghidra.py'
body = parent.read_text().replace('es-vector-source/ghidra', 'es-datadir-source/ghidra')
old = "[('ESP_GetTitleId', 'auto_03_802045CC_text.o', 38, 152), ('IOS_Ioctlv', 'auto_03_802045CC_text.o', 55, 220), ('fn_80242F60', 'auto_03_802045CC_text.o', 79, 316)]"
assert body.count(old) == 1
body = body.replace(old, "[('ESP_GetDataDir', 'auto_03_802045CC_text.o', 38, 152)]")
body = body.replace('ES title/vector spans172instructions/688bytes', 'ES data-dir span38instructions/152bytes').replace(
    'ORIGINAL_ES_TITLE_VECTOR_SPANS172_INSTRUCTIONS688_BYTES_DECODED', 'ORIGINAL_ES_DATADIR_SPAN38_INSTRUCTIONS152_BYTES_DECODED')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/es-datadir-source/ghidra/verification.json')
report = json.loads(path.read_text())
report['datadirParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Own DOL/decomp-toolkit span and independently discovered Ghidra body; SDK argument/null/alignment/vector control only.',
    'Not an executed service response, physical Wii or complete retail startup. Headless Ghidra; MCP unavailable.']
path.write_text(json.dumps(report, indent=2) + '\n')

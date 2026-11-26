"""Decode original SC status/next-file-or-finish functions independently of generated C++."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_es_datadir_ghidra.py')
body = parent.read_text().replace('es-datadir-source/ghidra', 'sysconf-completion-source/ghidra')
body = body.replace("[('ESP_GetDataDir', 'auto_03_802045CC_text.o', 38, 152)]",
    "[('SCCheckStatus', 'auto_03_802045CC_text.o', 71, 284), ('fn_80247980', 'auto_03_802045CC_text.o', 73, 292)]")
body = body.replace('ES data-dir span38instructions/152bytes', 'SC completion spans144instructions/576bytes').replace(
    'ORIGINAL_ES_DATADIR_SPAN38_INSTRUCTIONS152_BYTES_DECODED', 'ORIGINAL_SC_COMPLETION_SPANS144_INSTRUCTIONS576_BYTES_DECODED')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/sysconf-completion-source/ghidra/verification.json')
report = json.loads(path.read_text())
report['parentVerifierSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Original decomp-toolkit spans and independent Ghidra bodies; unresolved SDA globals are not runtime addresses.',
    'Native/original dynamic status/data comparisons are separate; headless/MCP unavailable, physical retail/cycles unverified.']
path.write_text(json.dumps(report, indent=2) + '\n')

"""Independently decode the first original DI86 wrapper and its callback."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_es_datadir_ghidra.py')
body = parent.read_text().replace('es-datadir-source/ghidra', 'di86-source/ghidra')
body = body.replace("[('ESP_GetDataDir', 'auto_03_802045CC_text.o', 38, 152)]",
    "[('fn_80227DD0', 'auto_03_802045CC_text.o', 90, 360), ('fn_802258A0', 'auto_03_802045CC_text.o', 46, 184)]")
body = body.replace('ES data-dir span38instructions/152bytes', 'DI86 wrapper/callback spans136instructions/544bytes').replace(
    'ORIGINAL_ES_DATADIR_SPAN38_INSTRUCTIONS152_BYTES_DECODED', 'ORIGINAL_DI86_WRAPPER_CALLBACK_SPANS136_INSTRUCTIONS544_BYTES_DECODED')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/di86-source/ghidra/verification.json')
report = json.loads(path.read_text())
report['parentVerifierSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Own DOL/decomp-toolkit wrapper span and independently discovered Ghidra body; DI command86/callback setup evidence.',
    'No executed DI86 response or physical drive proof; unresolved SDA labels are not runtime addresses. Headless, MCP unavailable.']
path.write_text(json.dumps(report, indent=2) + '\n')

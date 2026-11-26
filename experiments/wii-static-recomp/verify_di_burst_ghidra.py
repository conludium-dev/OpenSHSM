"""Decode the queued inquiry wrapper and synchronous ES initializer behind the native wait."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_es_datadir_ghidra.py')
body = parent.read_text().replace('es-datadir-source/ghidra', 'di-burst-source/ghidra')
body = body.replace("[('ESP_GetDataDir', 'auto_03_802045CC_text.o', 38, 152)]",
    "[('fn_80226CB0', 'auto_03_802045CC_text.o', 91, 364), ('ESP_InitLib', 'auto_03_802045CC_text.o', 21, 84)]")
body = body.replace('ES data-dir span38instructions/152bytes', 'DI inquiry/ES initializer spans112instructions/448bytes').replace(
    'ORIGINAL_ES_DATADIR_SPAN38_INSTRUCTIONS152_BYTES_DECODED', 'ORIGINAL_DI_INQUIRY_ES_INIT_SPANS112_INSTRUCTIONS448_BYTES_DECODED')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/di-burst-source/ghidra/verification.json')
report = json.loads(path.read_text())
report['parentVerifierSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Own DOL/decomp-toolkit spans and independent Ghidra bodies; queued native request origins, not original concurrent-burst behavior.',
    'No inquiry payload synthesized; unresolved SDA labels are not runtime addresses. Headless, MCP unavailable.']
path.write_text(json.dumps(report, indent=2) + '\n')

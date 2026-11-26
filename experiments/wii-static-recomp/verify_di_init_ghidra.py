"""Independently decode original DVD/DI startup rather than trust vendor HLE defaults."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_es_datadir_ghidra.py')
body = parent.read_text().replace('es-datadir-source/ghidra', 'di-init-source/ghidra')
body = body.replace("[('ESP_GetDataDir', 'auto_03_802045CC_text.o', 38, 152)]",
    "[('DVDLowInit', 'auto_03_802045CC_text.o', 153, 612), ('DVDInit', 'auto_03_802045CC_text.o', 85, 340)]")
body = body.replace('ES data-dir span38instructions/152bytes', 'DVD startup spans238instructions/952bytes').replace(
    'ORIGINAL_ES_DATADIR_SPAN38_INSTRUCTIONS152_BYTES_DECODED', 'ORIGINAL_DVD_STARTUP_SPANS238_INSTRUCTIONS952_BYTES_DECODED')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/di-init-source/ghidra/verification.json')
report = json.loads(path.read_text())
report['parentVerifierSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Original decomp-toolkit symbols/spans and independently discovered Ghidra bodies; static SDK evidence.',
    'DI ioctl results/disc data/physical drive/full retail init unverified. Unresolved SDA labels are not runtime addresses. Headless/MCP unavailable.']
path.write_text(json.dumps(report, indent=2) + '\n')

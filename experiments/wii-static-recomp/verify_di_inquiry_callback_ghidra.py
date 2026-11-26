"""Independently decode the actual upper inquiry callback before original burst replay."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_es_datadir_ghidra.py')
body = parent.read_text().replace('es-datadir-source/ghidra', 'di-inquiry-callback-source/ghidra')
body = body.replace("[('ESP_GetDataDir', 'auto_03_802045CC_text.o', 38, 152)]",
    "[('fn_80222F80', 'auto_03_802045CC_text.o', 632, 2528)]")
body = body.replace('ES data-dir span38instructions/152bytes', 'Inquiry upper callback span632instructions/2528bytes').replace(
    'ORIGINAL_ES_DATADIR_SPAN38_INSTRUCTIONS152_BYTES_DECODED', 'ORIGINAL_INQUIRY_UPPER_CALLBACK_SPAN632_INSTRUCTIONS2528_BYTES_DECODED')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/di-inquiry-callback-source/ghidra/verification.json')
report = json.loads(path.read_text())
report['parentVerifierSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Own DOL/decomp-toolkit upper callback span and independently discovered Ghidra body.',
    'Requires actual command-block/state preconditions; not original burst/inquiry response or physical-drive proof. SDA labels untrusted as runtime addresses.']
path.write_text(json.dumps(report, indent=2) + '\n')

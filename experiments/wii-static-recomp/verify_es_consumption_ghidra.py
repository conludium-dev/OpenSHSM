"""Independently decode the observed ES16 wrapper; its semantic name remains a lead."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_es_datadir_ghidra.py')
body = parent.read_text().replace('es-datadir-source/ghidra', 'es-consumption-source/ghidra').replace(
    "[('ESP_GetDataDir', 'auto_03_802045CC_text.o', 38, 152)]",
    "[('fn_80249CE0', 'auto_03_802045CC_text.o', 52, 208)]").replace(
    'ES data-dir span38instructions/152bytes', 'ES16 wrapper span52instructions/208bytes').replace(
    'ORIGINAL_ES_DATADIR_SPAN38_INSTRUCTIONS152_BYTES_DECODED', 'ORIGINAL_ES16_SPAN52_INSTRUCTIONS208_BYTES_DECODED')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/es-consumption-source/ghidra/verification.json')
report = json.loads(path.read_text())
report['parentVerifierSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Original Wii DOL/dtk wrapper and independently discovered Ghidra body, not service result.',
    'Command16/one input64/two outputs optional count-times8 array and count4; native capture separately identifies ticket ID, not title ID; SDA alias not runtime pointer.',
    'No callback/result/guard admission, retail boot, physical Wii or first-screen claim.']
path.write_text(json.dumps(report, indent=2) + '\n')

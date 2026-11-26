"""Independently decode the original SDK play-record start/callback, not execute it."""
from pathlib import Path
import json

parent = Path('experiments/wii-static-recomp/verify_es_datadir_ghidra.py')
body = parent.read_text().replace('es-datadir-source/ghidra', 'playrecord-source/ghidra').replace(
    "[('ESP_GetDataDir', 'auto_03_802045CC_text.o', 38, 152)]",
    "[('__OSStartPlayRecord', 'auto_03_802045CC_text.o', 21, 84), ('PlayRecordCallback_8021CDE0', 'auto_03_802045CC_text.o', 301, 1204)]").replace(
    'ES data-dir span38instructions/152bytes', 'playrecord start/callback spans322instructions/1288bytes').replace(
    'ORIGINAL_ES_DATADIR_SPAN38_INSTRUCTIONS152_BYTES_DECODED', 'ORIGINAL_PLAYRECORD_SPANS322_INSTRUCTIONS1288_BYTES_DECODED')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/playrecord-source/ghidra/verification.json')
report = json.loads(path.read_text())
report['limits'] = ['Original DOL/dtk spans and independently discovered Ghidra bodies; no live callback/IOS/file-write verification.',
    'Unresolved SDA and indirect state jump table make decompiled C insufficient to establish exact execution.',
    'Wii system-menu play_rec.dat is laboratory console bookkeeping, not a game asset or public runtime dependency.']
path.write_text(json.dumps(report, indent=2) + '\n')

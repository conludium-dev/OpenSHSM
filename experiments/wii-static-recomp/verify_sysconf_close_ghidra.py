"""Independently decode original NAND/SC close callbacks using decomp-toolkit spans."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_es_datadir_ghidra.py')
body = parent.read_text().replace('es-datadir-source/ghidra', 'sysconf-close-source/ghidra')
body = body.replace("[('ESP_GetDataDir', 'auto_03_802045CC_text.o', 38, 152)]",
    "[('fn_80245AF0', 'auto_03_802045CC_text.o', 23, 92), ('fn_802478F0', 'auto_03_802045CC_text.o', 35, 140)]")
body = body.replace('ES data-dir span38instructions/152bytes', 'NAND/SC close spans58instructions/232bytes').replace(
    'ORIGINAL_ES_DATADIR_SPAN38_INSTRUCTIONS152_BYTES_DECODED', 'ORIGINAL_NAND_SC_CLOSE_SPANS58_INSTRUCTIONS232_BYTES_DECODED')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/sysconf-close-source/ghidra/verification.json')
report = json.loads(path.read_text())
report['parentVerifierSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Own decomp-toolkit object symbols supply92/140-byte spans; Ghidra discovers bodies independently.',
    'Static callback-state/continuation evidence, not newly instrumented original close entry snapshots or physical Wii proof. Headless/MCP unavailable.']
path.write_text(json.dumps(report, indent=2) + '\n')

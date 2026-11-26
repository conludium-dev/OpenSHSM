"""Discover the original two-instruction PPCMtdec span independently."""
from pathlib import Path
import json

parent = Path('experiments/wii-static-recomp/verify_es_datadir_ghidra.py')
body = parent.read_text().replace('es-datadir-source/ghidra','playrecord-dec-source/ghidra').replace(
    "[('ESP_GetDataDir', 'auto_03_802045CC_text.o', 38, 152)]",
    "[('PPCMtdec', 'auto_03_802045CC_text.o', 2, 8)]").replace(
    'ES data-dir span38instructions/152bytes','PPCMtdec span2instructions/8bytes')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
path = Path('work/private-game/static-recomp/playrecord-dec-source/ghidra/verification.json')
report = json.loads(path.read_text())
report['result'] = 'ORIGINAL_PPCMTDEC_GHIDRA2_INSTRUCTIONS8_BYTES_DECODED'
report['limits'] = ['Own DOL/dtk SDK span and independently discovered Ghidra body, not DEC arithmetic/exception-delivery proof.',
    'Headless Ghidra; MCP unavailable. Dynamic original countdown captured separately.']
path.write_text(json.dumps(report,indent=2) + '\n')

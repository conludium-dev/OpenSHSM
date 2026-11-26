"""Independently decode original ticket-view wrapper without forcing Ghidra boundaries."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_es_datadir_ghidra.py')
body = parent.read_text().replace('es-datadir-source/ghidra', 'es-di-ticket-source/ghidra').replace(
    "[('ESP_GetDataDir', 'auto_03_802045CC_text.o', 38, 152)]",
    "[('ESP_DiGetTicketView', 'auto_03_802045CC_text.o', 41, 164)]").replace(
    'ES data-dir span38instructions/152bytes', 'ES DI-ticket-view span41instructions/164bytes').replace(
    'ORIGINAL_ES_DATADIR_SPAN38_INSTRUCTIONS152_BYTES_DECODED', 'ORIGINAL_ES_DI_TICKET_VIEW_SPAN41_INSTRUCTIONS164_BYTES_DECODED')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/es-di-ticket-source/ghidra/verification.json')
report = json.loads(path.read_text())
report['parentVerifierSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Original Wii DOL/dtk SDK wrapper span and independently discovered Ghidra body; not service execution or ticket response.',
    'Null optional ticket input has zero length, nonnull ticket676/outputview216, alignment32 enforced by original SDK.',
    'Unresolved SDA aliases not runtime pointers; headless local Ghidra, MCP unavailable.']
path.write_text(json.dumps(report, indent=2) + '\n')

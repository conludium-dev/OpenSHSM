"""Independently decode the measured-profile alternate BAT routine."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_memory_protection_ghidra.py')
body = parent.read_text().replace('dolphin-memory-protection', 'dolphin-memory936')
body = body.replace('fn_802180F0', 'fn_802181D0')
body = body.replace('MEMORY_PROTECTION_SELECTED_REAL_MODE_BAT_GHIDRA214_856_PASS',
    'MEMORY936_SELECTED_REAL_MODE_BAT_GHIDRA214_856_PASS')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-memory936/ghidra/verification.json')
report = json.loads(path.read_text())
report['profileRunnerSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Full discovered five bodies, alternate802181D0is53instructions/212bytes; no forced boundaries.',
    'Local Ghidra headless not MCP; decompiler is not original execution proof.',
    'Only measured direct-DOL936profile; other sizes and physical protection unverified.']
path.write_text(json.dumps(report, indent=2) + '\n')

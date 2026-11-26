"""Inspect the complete original DCZeroRange function."""
from pathlib import Path
import hashlib
import json
parent = Path('experiments/wii-static-recomp/verify_reset_code_ghidra.py')
body = parent.read_text().replace('dolphin-reset-code', 'dolphin-dc-zero').replace('OSGetResetCode', 'DCZeroRange')
body = body.replace('12, 48', '11, 44').replace('12instructions/48bytes', '11instructions/44bytes')
body = body.replace('RESET_CODE_GHIDRA_FULL12_48_PASS', 'DC_ZERO_GHIDRA_FULL11_44_PASS')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-dc-zero/ghidra/verification.json')
report = json.loads(path.read_text())
report['resetParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Full11instructions/44-byte discovered body, no forced boundaries; local headless, not MCP.',
    'dcbz semantics/physical timing are not established by decompiler output.']
path.write_text(json.dumps(report, indent=2) + '\n')

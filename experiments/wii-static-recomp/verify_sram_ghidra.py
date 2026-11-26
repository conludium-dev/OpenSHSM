"""Inspect original SRAM, DMA and unlock bodies in the existing private SDK project."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_si_irq_ghidra.py')
body = parent.read_text()
before = "repr([('SIInterruptHandler', 'auto_03_802045CC_text.o', 251, 1004)])"
after = "repr([('__OSInitSram', 'auto_03_802045CC_text.o', 128, 512), ('EXIDma', 'auto_03_802045CC_text.o', 62, 248), ('UnlockSram', 'auto_03_802045CC_text.o', 184, 736)])"
assert body.count(before) == 1
body = body.replace(before, after).replace('dolphin-si-irq', 'dolphin-sram')
body = body.replace("assert report['records'][0]['discoveredBodyBytes'] == 1004", "assert all(row['discoveredBodyBytes'] == row['bytes'] for row in report['records'])")
body = body.replace('SI_IRQ_HANDLER_GHIDRA251_INSTRUCTIONS1004_BYTES_FULL_BODY', 'SRAM_DMA_UNLOCK_GHIDRA374_INSTRUCTIONS1496_BYTES_FULL_BODIES')
body = body.replace('PASS SIInterruptHandler Ghidra251instructions/1004span bytes', 'PASS SRAM/DMA/UnlockSram Ghidra374instructions/1496span bytes')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-sram/ghidra/verification.json')
report = json.loads(path.read_text())
report['parentRunnerSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Independent discovered bodies in the existing relocatable dtk SDK object, no forced boundaries.',
    'Behavior/DMA/cache verified separately; no retail startup/physical Wii claim. Headless Ghidra, not MCP.']
path.write_text(json.dumps(report, indent=2) + '\n')

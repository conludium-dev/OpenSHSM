"""Verify the full original audio-clock body in the existing private SDK project."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_si_irq_ghidra.py')
body = parent.read_text().replace("repr([('SIInterruptHandler', 'auto_03_802045CC_text.o', 251, 1004)])",
    "repr([('__AIClockInit', 'auto_03_802045CC_text.o', 136, 544)])")
body = body.replace('dolphin-si-irq', 'dolphin-ai-clock').replace("== 1004", "== 544")
body = body.replace('SI_IRQ_HANDLER_GHIDRA251_INSTRUCTIONS1004_BYTES_FULL_BODY', 'AI_CLOCK_GHIDRA136_INSTRUCTIONS544_BYTES_FULL_BODY')
body = body.replace('PASS SIInterruptHandler Ghidra251instructions/1004span bytes', 'PASS __AIClockInit Ghidra136instructions/544span bytes')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-ai-clock/ghidra/verification.json')
report = json.loads(path.read_text())
report['parentRunnerSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Full discovered136/544body, no forced boundary; clock-register/tick behavior verified separately.', 'Headless Ghidra, not MCP; no physical Wii acceptance.']
path.write_text(json.dumps(report, indent=2) + '\n')

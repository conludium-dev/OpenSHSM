"""Inspect the full original reset-code function in the existing dtk object."""
from pathlib import Path
import hashlib
import json
parent = Path('experiments/wii-static-recomp/verify_frsp_roots_ghidra.py')
body = parent.read_text()
old = "[('fn_801015CC', 'auto_03_80100D70_text.o', 54, 216),\n                                    ('fn_801123DC', 'auto_03_8010EE1C_text.o', 115, 460)]"
assert body.count(old) == 1
body = body.replace(old, repr([('OSGetResetCode', 'auto_03_802045CC_text.o', 12, 48)]))
body = body.replace("output = private / 'frsp-roots/ghidra'", "output = private / 'dolphin-reset-code/ghidra'")
body = body.replace("project = 'shsm-frsp-roots-' + name", "project = 'shsm-irq-primitives-OSDisableInterrupts'")
body = body.replace('str(output), project,', "str(private / 'ios-thread-cycle-irqs/ghidra'), project,")
body = body.replace("(output / (project + '.gpr')).exists()", "(private / 'ios-thread-cycle-irqs/ghidra' / (project + '.gpr')).exists()")
body = body.replace('PASS two scalar roots Ghidra169instructions/676bytes/decompilation; paired root/runtime behavior pending', 'PASS reset-code Ghidra12instructions/48bytes')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-reset-code/ghidra/verification.json')
report = json.loads(path.read_text())
report['result'] = 'RESET_CODE_GHIDRA_FULL12_48_PASS'
report['parentRunnerSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Full discovered body, no forced boundaries; local headless, not MCP.', 'Decompiler output is not physical reset behavior proof.']
path.write_text(json.dumps(report, indent=2) + '\n')

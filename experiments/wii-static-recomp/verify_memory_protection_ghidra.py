"""Inspect complete original memory-protection and selected real-mode BAT bodies."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_frsp_roots_ghidra.py')
body = parent.read_text()
old = "[('fn_801015CC', 'auto_03_80100D70_text.o', 54, 216),\n                                    ('fn_801123DC', 'auto_03_8010EE1C_text.o', 115, 460)]"
assert body.count(old) == 1
body = body.replace(old, repr([(name, 'auto_03_802045CC_text.o', count, size) for name, count, size in
    [('__OSInitMemoryProtection', 51, 204), ('BATConfig', 72, 288), ('fn_802184F0', 6, 24),
     ('fn_80218070', 32, 128), ('fn_802180F0', 53, 212)]]))
body = body.replace("output = private / 'frsp-roots/ghidra'", "output = private / 'dolphin-memory-protection/ghidra'")
body = body.replace("project = 'shsm-frsp-roots-' + name", "project = 'shsm-irq-primitives-OSDisableInterrupts'")
body = body.replace('str(output), project,', "str(private / 'ios-thread-cycle-irqs/ghidra'), project,")
body = body.replace("(output / (project + '.gpr')).exists()", "(private / 'ios-thread-cycle-irqs/ghidra' / (project + '.gpr')).exists()")
body = body.replace('PASS two scalar roots Ghidra169instructions/676bytes/decompilation; paired root/runtime behavior pending',
    'PASS memory-protection/selected BAT Ghidra214instructions/856bytes')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-memory-protection/ghidra/verification.json')
report = json.loads(path.read_text())
report['result'] = 'MEMORY_PROTECTION_SELECTED_REAL_MODE_BAT_GHIDRA214_856_PASS'
report['parentRunnerSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Full five discovered bodies in existing decomp-toolkit object, no forced boundaries; local headless, not MCP.',
    'Selected24MB MEM1/64MB MEM2 profile only; other BAT alternatives/physical protection/CPU interrupt delivery unverified.',
    'Decompiler C is not execution proof; original unpatched16calls provide separate endpoint evidence.']
path.write_text(json.dumps(report, indent=2) + '\n')

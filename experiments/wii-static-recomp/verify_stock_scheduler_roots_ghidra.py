"""Inspect original scheduler/suspend gate in the existing private SDK Ghidra project."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_frsp_roots_ghidra.py')
body = parent.read_text()
old = "[('fn_801015CC', 'auto_03_80100D70_text.o', 54, 216),\n                                    ('fn_801123DC', 'auto_03_8010EE1C_text.o', 115, 460)]"
assert body.count(old) == 1
body = body.replace(old, repr([('SelectThread', 'auto_03_802045CC_text.o', 87, 348),
    ('fn_8021B0B0', 'auto_03_802045CC_text.o', 24, 96)]))
body = body.replace("output = private / 'frsp-roots/ghidra'", "output = private / 'stock-baseline/headless-scheduler-observe/ghidra'")
body = body.replace("project = 'shsm-frsp-roots-' + name", "project = 'shsm-irq-primitives-OSDisableInterrupts'")
body = body.replace('str(output), project,', "str(private / 'ios-thread-cycle-irqs/ghidra'), project,")
body = body.replace("(output / (project + '.gpr')).exists()", "(private / 'ios-thread-cycle-irqs/ghidra' / (project + '.gpr')).exists()")
body = body.replace("'-scriptPath',", "'-readOnly', '-scriptPath',")
body = body.replace('ExportRootCheck.java', 'ExportFormatSpan.java')
body = body.replace("'instructions': count, 'bytes': size,", "'instructions': count, 'bytes': size, 'discoveredBodyBytes': int((output / 'function-body-bytes.txt').read_text()),")
body = body.replace('PASS two scalar roots Ghidra169instructions/676bytes/decompilation; paired root/runtime behavior pending',
    'SCHEDULER_SUSPEND_GATE_GHIDRA_PREFIX_PASS')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/stock-baseline/headless-scheduler-observe/ghidra/verification.json')
report = json.loads(path.read_text())
report['result'] = 'ORIGINAL_SCHEDULER_IDLE_AND_SUSPEND_GATE_GHIDRA_PREFIX_PASS'
report['parentRunnerSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Own dtk SDK object,111scalar PPC instructions/444prefix bytes; not complete scheduler/ResumeThread body equivalence.',
    'SelectThread name recovered by dtk; function8021B0B0 resume role inferred from verified decrement/state gate.',
    'Existing SDK Ghidra project read-only; Ghidra MCP not available, local headless used.',
    'No live scheduling, queue insertion, original Wii hardware or native stall-resolution proof.']
path.write_text(json.dumps(report, indent=2) + '\n')

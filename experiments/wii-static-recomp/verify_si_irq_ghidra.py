"""Verify the original SI interrupt-handler span in the existing SDK project."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'verify_frsp_roots_ghidra.py'
body = builder.read_text()
old = "[('fn_801015CC', 'auto_03_80100D70_text.o', 54, 216),\n                                    ('fn_801123DC', 'auto_03_8010EE1C_text.o', 115, 460)]"
assert body.count(old) == 1
body = body.replace(old, repr([('SIInterruptHandler', 'auto_03_802045CC_text.o', 251, 1004)]))
body = body.replace("output = private / 'frsp-roots/ghidra'", "output = private / 'dolphin-si-irq/ghidra'")
body = body.replace("project = 'shsm-frsp-roots-' + name", "project = 'shsm-irq-primitives-OSDisableInterrupts'")
body = body.replace('str(output), project,', "str(private / 'ios-thread-cycle-irqs/ghidra'), project,")
body = body.replace("(output / (project + '.gpr')).exists()", "(private / 'ios-thread-cycle-irqs/ghidra' / (project + '.gpr')).exists()")
body = body.replace('ExportRootCheck.java', 'ExportFormatSpan.java')
body = body.replace("'instructions': count, 'bytes': size,", "'instructions': count, 'bytes': size, 'discoveredBodyBytes': int((output / 'function-body-bytes.txt').read_text()),")
body = body.replace('PASS two scalar roots Ghidra169instructions/676bytes/decompilation; paired root/runtime behavior pending', 'PASS SIInterruptHandler Ghidra251instructions/1004span bytes')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-si-irq/ghidra/verification.json')
report = json.loads(path.read_text())
assert report['records'][0]['discoveredBodyBytes'] == 1004
report['result'] = 'SI_IRQ_HANDLER_GHIDRA251_INSTRUCTIONS1004_BYTES_FULL_BODY'
report['baseRunnerSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['limits'] = ['Independent discovered body/span verification in relocatable dtk object; original behavior checked separately.',
    'No forced boundary, automatic CPU exception-vector delivery, physical Wii or full SI/controller proof. Headless, not MCP.']
path.write_text(json.dumps(report, indent=2) + '\n')

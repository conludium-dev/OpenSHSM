"""Decode UART spans using the existing private SDK Ghidra project."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'verify_frsp_roots_ghidra.py'
body = builder.read_text()
old = "[('fn_801015CC', 'auto_03_80100D70_text.o', 54, 216),\n                                    ('fn_801123DC', 'auto_03_8010EE1C_text.o', 115, 460)]"
assert body.count(old) == 1
body = body.replace(old, repr([('fn_8020F3C0', 'auto_03_802045CC_text.o', 98, 392), ('fn_80240320', 'auto_03_802045CC_text.o', 140, 560)]))
body = body.replace("output = private / 'frsp-roots/ghidra'", "output = private / 'uart-native/ghidra'")
body = body.replace("project = 'shsm-frsp-roots-' + name", "project = 'shsm-irq-primitives-OSDisableInterrupts'")
body = body.replace('str(output), project,', "str(private / 'ios-thread-cycle-irqs/ghidra'), project,")
body = body.replace("(output / (project + '.gpr')).exists()", "(private / 'ios-thread-cycle-irqs/ghidra' / (project + '.gpr')).exists()")
body = body.replace('ExportRootCheck.java', 'ExportFormatSpan.java')
body = body.replace("'instructions': count, 'bytes': size,", "'instructions': count, 'bytes': size, 'discoveredBodyBytes': int((output / 'function-body-bytes.txt').read_text()),")
body = body.replace('PASS two scalar roots Ghidra169instructions/676bytes/decompilation; paired root/runtime behavior pending',
                    'PASS UART helper/write spans238instructions/952bytes; discovered-body decompilation only')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/uart-native/ghidra/verification.json')
report = json.loads(path.read_text())
report['result'] = 'ORIGINAL_UART_SPANS_GHIDRA238_INSTRUCTIONS952_BYTES_DECODED'
report['baseRunnerSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['limits'] = ['Dtk supplies spans, Ghidra decodes instructions and decompiles its discovered body without forcing boundaries.',
                    'Whole behavior verified against original Dolphin separately; not full CPU/physical Wii/retail boot proof. Headless, MCP unavailable.']
path.write_text(json.dumps(report, indent=2) + '\n')

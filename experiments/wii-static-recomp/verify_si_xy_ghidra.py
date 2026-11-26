"""Independently decode SISetXY in the existing private SDK project."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'verify_frsp_roots_ghidra.py'
body = builder.read_text()
old = "[('fn_801015CC', 'auto_03_80100D70_text.o', 54, 216),\n                                    ('fn_801123DC', 'auto_03_8010EE1C_text.o', 115, 460)]"
assert body.count(old) == 1
body = body.replace(old, repr([('SISetXY', 'auto_03_802045CC_text.o', 23, 92)]))
body = body.replace("output = private / 'frsp-roots/ghidra'", "output = private / 'si-xy-native/ghidra'")
body = body.replace("project = 'shsm-frsp-roots-' + name", "project = 'shsm-irq-primitives-OSDisableInterrupts'")
body = body.replace('str(output), project,', "str(private / 'ios-thread-cycle-irqs/ghidra'), project,")
body = body.replace("(output / (project + '.gpr')).exists()", "(private / 'ios-thread-cycle-irqs/ghidra' / (project + '.gpr')).exists()")
body = body.replace('ExportRootCheck.java', 'ExportFormatSpan.java')
body = body.replace("'instructions': count, 'bytes': size,", "'instructions': count, 'bytes': size, 'discoveredBodyBytes': int((output / 'function-body-bytes.txt').read_text()),")
body = body.replace('PASS two scalar roots Ghidra169instructions/676bytes/decompilation; paired root/runtime behavior pending', 'PASS SISetXY Ghidra23instructions/92span bytes')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/si-xy-native/ghidra/verification.json')
report = json.loads(path.read_text())
assert report['records'][0]['discoveredBodyBytes'] == 92
report['result'] = 'SI_SET_XY_GHIDRA23_INSTRUCTIONS92_BYTES_FULL_BODY'
report['baseRunnerSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['limits'] = ['Independent discovered body/span verification; behavior uses separate original-code capture. No physical-Wii/full SI initialization proof.']
path.write_text(json.dumps(report, indent=2) + '\n')

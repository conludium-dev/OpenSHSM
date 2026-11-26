"""Use the existing independent dtk/Ghidra exporter for the complete parser."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'verify_frsp_roots_ghidra.py'
body = builder.read_text()
old = "[('fn_801015CC', 'auto_03_80100D70_text.o', 54, 216),\n                                    ('fn_801123DC', 'auto_03_8010EE1C_text.o', 115, 460)]"
assert body.count(old) == 1
body = body.replace(old, repr([('parse_format_80199A24', 'auto_03_8018FEA8_text.o', 367, 1468)]))
body = body.replace("output = private / 'frsp-roots/ghidra'", "output = private / 'format-parse/ghidra'")
body = body.replace('shsm-frsp-roots-', 'shsm-format-root-')
body = body.replace('ExportRootCheck.java', 'ExportFormatSpan.java')
body = body.replace('PASS two scalar roots Ghidra169instructions/676bytes/decompilation; paired root/runtime behavior pending',
                    'PASS original format parser Ghidra367instructions/1468bytes/decompilation')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/format-parse/ghidra/verification.json')
report = json.loads(path.read_text())
report['result'] = 'ORIGINAL_FORMAT_GHIDRA367_INSTRUCTION_SPAN_PARTIAL_FUNCTION_DECOMPILATION'
report['discoveredFunctionBodyBytes'] = int((path.parent / 'function-body-bytes.txt').read_text())
report['baseRunnerSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['limits'] = ['Dtk supplies1468-byte span; Ghidra decodes367instructions but discovers only a partial function body, without manually changing its boundary.',
                    'Decompilation covers the discovered partial body only; behavior verified separately against complete PPC execution.',
                    'Relocatable object addresses, no full OSReport/boot proof; headless Ghidra, MCP unavailable.']
path.write_text(json.dumps(report, indent=2) + '\n')

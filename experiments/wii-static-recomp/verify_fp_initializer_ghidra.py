"""Independently discover the complete original integer-to-single initializer."""
from pathlib import Path
import ast
import json

parent = Path('experiments/wii-static-recomp/verify_frsp_roots_ghidra.py')
body = parent.read_text().replace('frsp-roots/ghidra','fp-initializer-source/ghidra').replace(
    'shsm-frsp-roots-','shsm-fp-initializer-').replace('ExportRootCheck.java','ExportFormatSpan.java')
node = next(node for node in ast.parse(body).body if isinstance(node,ast.For))
body = body.replace(ast.get_source_segment(body,node.iter),repr([('fn_8000C2F4','auto_fn_8000C2F4_text.o',14,56)]))
body = body.replace("'instructions': count, 'bytes': size,", "'instructions': count, 'bytes': size, 'discoveredBodyBytes': int((output / 'function-body-bytes.txt').read_text()),")
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
path = Path('work/private-game/static-recomp/fp-initializer-source/ghidra/verification.json')
report = json.loads(path.read_text())
report['result'] = 'ORIGINAL_FP_INITIALIZER_GHIDRA14_INSTRUCTIONS56_BYTES_DECODED'
report['limits'] = ['Own DOL/dtk object span and independently discovered Ghidra body; not live FP behavior.',
    'SDA decompiler labels are not runtime pointers; headless Ghidra, MCP unavailable.']
path.write_text(json.dumps(report,indent=2) + '\n')

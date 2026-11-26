"""Inspect original flush/vector/installer spans in the existing SDK project."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_frsp_roots_ghidra.py')
body = parent.read_text()
old = "[('fn_801015CC', 'auto_03_80100D70_text.o', 54, 216),\n                                    ('fn_801123DC', 'auto_03_8010EE1C_text.o', 115, 460)]"
assert body.count(old) == 1
body = body.replace(old, repr([('DCFlushRange', 'auto_03_802045CC_text.o', 12, 48),
    ('fn_8021A120', 'auto_03_802045CC_text.o', 7, 28), ('__OSInitSystemCall', 'auto_03_802045CC_text.o', 24, 96)]))
body = body.replace("output = private / 'frsp-roots/ghidra'", "output = private / 'dolphin-flush-syscall/ghidra'")
body = body.replace("project = 'shsm-frsp-roots-' + name", "project = 'shsm-irq-primitives-OSDisableInterrupts'")
body = body.replace('str(output), project,', "str(private / 'ios-thread-cycle-irqs/ghidra'), project,")
body = body.replace("(output / (project + '.gpr')).exists()", "(private / 'ios-thread-cycle-irqs/ghidra' / (project + '.gpr')).exists()")
body = body.replace('ExportRootCheck.java', 'ExportFormatSpan.java')
body = body.replace("'instructions': count, 'bytes': size,", "'instructions': count, 'bytes': size, 'discoveredBodyBytes': int((output / 'function-body-bytes.txt').read_text()),")
body = body.replace('PASS two scalar roots Ghidra169instructions/676bytes/decompilation; paired root/runtime behavior pending', 'PASS syscall flush/vector/installer Ghidra spans')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-flush-syscall/ghidra/verification.json')
report = json.loads(path.read_text())
report['result'] = 'DCFLUSH_SYSCALL_VECTOR_INSTALLER_GHIDRA_SPANS'
report['parentRunnerSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Headless Ghidra, not MCP; SDK relocatable object, no forced boundaries. Discovered body sizes recorded.',
    'Copied vector is7instructions/28bytes; declared32-byte toolkit function includes unreachable trailing nop outside the copied span.',
    'Original CPU/cache behavior measured separately; no physical hardware ordering or native syscall delivery proof.']
path.write_text(json.dumps(report, indent=2) + '\n')

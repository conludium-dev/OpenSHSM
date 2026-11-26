"""Inspect original lazy-FPU switch/load/context roots in the existing private SDK project."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'verify_frsp_roots_ghidra.py'
body = parent.read_text()
old = "[('fn_801015CC', 'auto_03_80100D70_text.o', 54, 216),\n                                    ('fn_801123DC', 'auto_03_8010EE1C_text.o', 115, 460)]"
assert body.count(old) == 1
body = body.replace(old, repr([('OSSwitchFPUContext', 'auto_03_802045CC_text.o', 33, 132),
    ('__OSLoadFPUContext', 'auto_03_802045CC_text.o', 3, 12),
    ('OSSetCurrentContext', 'auto_03_802045CC_text.o', 23, 92),
    ('__OSContextInit', 'auto_03_802045CC_text.o', 18, 72)]))
body = body.replace("output = private / 'frsp-roots/ghidra'", "output = private / 'dolphin-fpu-lazy/ghidra'")
body = body.replace("project = 'shsm-frsp-roots-' + name", "project = 'shsm-irq-primitives-OSDisableInterrupts'")
body = body.replace('str(output), project,', "str(private / 'ios-thread-cycle-irqs/ghidra'), project,")
body = body.replace("(output / (project + '.gpr')).exists()", "(private / 'ios-thread-cycle-irqs/ghidra' / (project + '.gpr')).exists()")
body = body.replace('ExportRootCheck.java', 'ExportFormatSpan.java')
body = body.replace("'instructions': count, 'bytes': size,", "'instructions': count, 'bytes': size, 'discoveredBodyBytes': int((output / 'function-body-bytes.txt').read_text()),")
body = body.replace('PASS two scalar roots Ghidra169instructions/676bytes/decompilation; paired root/runtime behavior pending', 'PASS lazy-FPU Ghidra roots; paired decode and runtime limitations recorded separately')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-fpu-lazy/ghidra/verification.json')
report = json.loads(path.read_text())
report['result'] = 'LAZY_FPU_SWITCH_CONTEXT_ROOTS_AND_EMPTY_LOAD_GATE_GHIDRA'
report['parentRunnerSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Own SDK relocatable object disassembly/decompilation; no forced boundaries. Discovered body sizes recorded per root.',
    'Only the first3instructions/12bytes of __OSLoadFPUContext are span-verified, not its full292-byte body or decompiled populated path.',
    'Default PPC language can misdecode paired singles in populated load path; first-use empty-context runtime proof does not execute that path.',
    'Headless Ghidra, not MCP; native delivery, prior-owner save/restoration and full FPU/physical Wii remain unverified.']
path.write_text(json.dumps(report, indent=2) + '\n')

"""Inspect the complete original SDK audio initialization body in the existing project."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_frsp_roots_ghidra.py')
body = parent.read_text()
old = "[('fn_801015CC', 'auto_03_80100D70_text.o', 54, 216),\n                                    ('fn_801123DC', 'auto_03_8010EE1C_text.o', 115, 460)]"
assert body.count(old) == 1
body = body.replace(old, repr([('__OSInitAudioSystem', 'auto_03_802045CC_text.o', 116, 464)]))
body = body.replace("output = private / 'frsp-roots/ghidra'", "output = private / 'dolphin-audio-init/ghidra'")
body = body.replace("project = 'shsm-frsp-roots-' + name", "project = 'shsm-irq-primitives-OSDisableInterrupts'")
body = body.replace('str(output), project,', "str(private / 'ios-thread-cycle-irqs/ghidra'), project,")
body = body.replace("(output / (project + '.gpr')).exists()", "(private / 'ios-thread-cycle-irqs/ghidra' / (project + '.gpr')).exists()")
body = body.replace('ExportRootCheck.java', 'ExportAudioInitSpan.java')
body = body.replace("'instructions': count, 'bytes': size,", "'instructions': count, 'bytes': size, 'discoveredBodyBytes': int((output / 'function-body-bytes.txt').read_text()),")
body = body.replace('PASS two scalar roots Ghidra169instructions/676bytes/decompilation; paired root/runtime behavior pending', 'PASS original OS audio initialization Ghidra116/464')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-audio-init/ghidra/verification.json')
report = json.loads(path.read_text())
membership = (path.parent / 'body-membership.txt').read_text().splitlines()
assert len(membership) == 116
assert [int(line.split('\t')[0]) for line in membership if line.endswith('\tfalse')] == [0x15c]
assert report['records'][0]['discoveredBodyBytes'] == 460
report['result'] = 'OS_AUDIO_INIT_GHIDRA116_SPAN_DISCOVERED460_EXCLUDES_UNREACHABLE_NOP'
report['membershipSha256'] = hashlib.sha256((path.parent / 'body-membership.txt').read_bytes()).hexdigest()
report['parentRunnerSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['All116instructions/464-byte span decoded; discovered460-byte body excludes only unreachable nop80212E3C, no forced boundaries.',
    'Decompiler shows infinite MMIO polling and does not establish later runtime behavior; original16whole-function returns are independent evidence.',
    'Headless Ghidra, not MCP; DSP HLE/reference behavior does not prove physical Wii or native audio output.']
path.write_text(json.dumps(report, indent=2) + '\n')

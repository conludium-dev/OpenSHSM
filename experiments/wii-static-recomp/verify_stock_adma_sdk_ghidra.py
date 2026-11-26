"""Check owned Wii DMA setup/start/stop/count/init bodies with DTK bytes and existing Ghidra project."""
from pathlib import Path
import hashlib
import json
import re
import struct

root = Path('.').resolve()
private = root / 'work/private-game/static-recomp'
public = root / 'experiments/wii-static-recomp'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
dol_path = root / 'work/private-game/disc/DATA/sys/main.dol'
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
layout = struct.unpack('>64I', dol[:256])
asm = private / 'dtk-output/asm/auto_03_802045CC_text.s'
(private / 'stock-adma-sdk/ghidra').mkdir(parents=True, exist_ok=True)
text = asm.read_text()
roots = [('fn_8022CAB0', 31, 124), ('fn_8022CB30', 5, 20), ('fn_8022CB50', 5, 20),
    ('fn_8022CB70', 4, 16), ('fn_8022CBC0', 96, 384)]
for name, count, size in roots:
    body = text.split('.fn ' + name + ',')[1].split('.endfn ' + name)[0]
    words = re.findall(r'/\* ([0-9A-F]{8}) [0-9A-F]{8}  ((?:[0-9A-F]{2} ){3}[0-9A-F]{2}) \*/', body)
    assert len(words) == count and count * 4 == size
    for address_text, word in words:
        address = int(address_text, 16)
        section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
        offset = layout[section] + address - layout[18 + section]
        assert dol[offset:offset + 4] == bytes.fromhex(word)
base = public / 'verify_frsp_roots_ghidra.py'
script = base.read_text()
old = "[('fn_801015CC', 'auto_03_80100D70_text.o', 54, 216),\n                                    ('fn_801123DC', 'auto_03_8010EE1C_text.o', 115, 460)]"
assert script.count(old) == 1
script = script.replace(old, repr([(name, 'auto_03_802045CC_text.o', count, size) for name, count, size in roots]))
script = script.replace("output = private / 'frsp-roots/ghidra'", "output = private / 'stock-adma-sdk/ghidra'")
script = script.replace("project = 'shsm-frsp-roots-' + name", "project = 'shsm-irq-primitives-OSDisableInterrupts'")
script = script.replace('str(output), project,', "str(private / 'ios-thread-cycle-irqs/ghidra'), project,")
script = script.replace("(output / (project + '.gpr')).exists()", "(private / 'ios-thread-cycle-irqs/ghidra' / (project + '.gpr')).exists()")
script = script.replace('ExportRootCheck.java', 'ExportFormatSpan.java')
script = script.replace('PASS two scalar roots Ghidra169instructions/676bytes/decompilation; paired root/runtime behavior pending',
    'PASS five owned Wii ADMA SDK roots Ghidra141instructions/564bytes/decompilation')
script = script.replace("'instructions': count, 'bytes': size,", "'instructions': count, 'bytes': size, 'discoveredBodyBytes': int((output / 'function-body-bytes.txt').read_text()),")
exec(compile(script, str(base), 'exec'), {'__file__': __file__})
path = private / 'stock-adma-sdk/ghidra/verification.json'
report = json.loads(path.read_text())
assert all(row['bytes'] == row['discoveredBodyBytes'] for row in report['records'])
report.update(result='OWN_WII_ADMA_SDK_DTK_GHIDRA141_WORDS564_BYTES', originalDolSha256=sha(dol_path),
    dtkAssemblySha256=sha(asm), baseRunnerSha256=sha(base),
    scriptSha256=sha(public / 'ExportFormatSpan.java'),
    limits=['Own Wii DOL words match DTK; independent Ghidra full discovered bodies/decompilation.',
        'Function role inferred from register accesses, not recovered original names; runtime/latching/device timing separate.'])
path.write_text(json.dumps(report, indent=2) + '\n')
print('OWN_WII_ADMA_SDK_DTK_GHIDRA141_WORDS564_BYTES')

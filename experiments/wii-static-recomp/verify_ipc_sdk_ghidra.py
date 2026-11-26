"""Independently inspect the existing dtk register helpers without executing original senders."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'verify_frsp_roots_ghidra.py'
body = builder.read_text().replace("output = private / 'frsp-roots/ghidra'", "output = private / 'ipc-sdk-roots/ghidra'")
body = body.replace("[('fn_801015CC', 'auto_03_80100D70_text.o', 54, 216),\n                                    ('fn_801123DC', 'auto_03_8010EE1C_text.o', 115, 460)]",
                    "[('IPCReadReg', 'auto_03_802045CC_text.o', 4, 16), ('IPCWriteReg', 'auto_03_802045CC_text.o', 4, 16)]")
assert "('IPCReadReg', 'auto_03_802045CC_text.o', 4, 16)" in body
body = body.replace('shsm-frsp-roots-', 'shsm-ipc-sdk-')
body = body.replace('PASS two scalar roots Ghidra169instructions/676bytes/decompilation; paired root/runtime behavior pending',
                    'PASS scoped IPC helper Ghidra boundaries/decompilation')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/ipc-sdk-roots/ghidra/verification.json')
report = json.loads(path.read_text())
report['result'] = 'TWO_ORIGINAL_IPC_REGISTER_HELPERS_GHIDRA8_INSTRUCTIONS32_BYTES_PASS'
report['baseRunnerSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['limits'] = ['Existing dtk SDK-label boundaries independently disassembled/decompiled by headless Ghidra.',
                    'No sender/runtime ABI or native/original hardware behavior execution proof; Ghidra MCP unavailable.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS IPCReadReg/IPCWriteReg Ghidra8instructions/32bytes; sender integration pending')

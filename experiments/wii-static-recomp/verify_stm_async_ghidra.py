"""Independent dtk/Ghidra SDK body evidence for STM initialization and async callback."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_frsp_roots_ghidra.py')
Path('work/private-game/static-recomp/stm-async-source/ghidra').mkdir(parents=True, exist_ok=True)
body = parent.read_text().replace("output = private / 'frsp-roots/ghidra'", "output = private / 'stm-async-source/ghidra'")
old = "[('fn_801015CC', 'auto_03_80100D70_text.o', 54, 216),\n                                    ('fn_801123DC', 'auto_03_8010EE1C_text.o', 115, 460)]"
assert body.count(old) == 1
body = body.replace(old, "[('__OSInitSTM', 'auto_03_802045CC_text.o', 70, 280), ('IOS_IoctlAsync', 'auto_03_802045CC_text.o', 78, 312), ('__OSStateEventHandler', 'auto_03_802045CC_text.o', 85, 340)]")
body = body.replace('shsm-frsp-roots-', 'shsm-stm-async-')
body = body.replace('PASS two scalar roots Ghidra169instructions/676bytes/decompilation; paired root/runtime behavior pending',
    'PASS STM SDK Ghidra233instructions/932bytes; runtime behavior pending')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/stm-async-source/ghidra/verification.json')
report = json.loads(path.read_text())
report['result'] = 'STM_INIT_ASYNC_IOCTL_EVENT_HANDLER_GHIDRA233_INSTRUCTIONS932_BYTES_PASS'
report['baseRunnerSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Own Wii dtk SDK-labelled function boundaries/assembly/decompilation, not runtime equivalence or IOCTL completion proof.',
    'Headless local Ghidra; Ghidra MCP unavailable. Generated original code remains private.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS Ghidra STM init/async IOCTL/event handler;233instructions/932bytes; behavior still requires original execution')

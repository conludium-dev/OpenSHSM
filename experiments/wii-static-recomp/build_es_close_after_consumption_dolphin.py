"""Execute whole original ESP_CloseLib after the verified original ES16 chain."""
from pathlib import Path
import ast
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_es_consumption_dolphin.py')
body = parent.read_text().replace('dolphin-es-consumption', 'dolphin-es-close-after-consumption').replace(
    'run_es_consumption_disc_dolphin.ps1', 'run_es_close_after_consumption_disc_dolphin.ps1')
node = next(node for node in ast.parse(body).body if isinstance(node, ast.Assign) and
    any(isinstance(target, ast.Name) and target.id == 'extra' for target in node.targets))
extra = ast.literal_eval(node.value)
extra += '''code.append(branch(text + len(code) * 4, 0x802497f0, True))
pointer(code, 12, 0x806f4260)
code.extend([dform(36, 3, 12, 0), 0x7c0000a6, dform(36, 0, 12, 4)])
pointer(code, 11, 0x80528ce8)
code.extend([dform(32, 0, 11, 0), dform(36, 0, 12, 8)])
pointer(code, 3, 0x806f4260)
code.append(dform(14, 4, 0, 32))
code.append(branch(text + len(code) * 4, 0x80212fd0, True))
'''
body = body.replace(ast.get_source_segment(body, node.value), repr(extra))
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-es-close-after-consumption/generation.json')
report = json.loads(path.read_text())
report['closeParentGeneratorSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['closeOracle'] = {'target': 0x802497f0, 'scalars': 0x806f4260, 'sdkFdAddress': 0x80528ce8}
report['limits'] = ['Whole original DVD/ES/ticket/ES16 chain followed by whole ESP_CloseLib.',
    'Original SDK/kernel own request/result/FD clearing/free; helper captures result/MSR/SDK fd then original flush.',
    'Dolphin LAB is not physical Wii/cache timing; original close completion still requires live capture.']
path.write_text(json.dumps(report, indent=2) + '\n')

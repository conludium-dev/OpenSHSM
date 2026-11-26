"""Compile original alternate BAT body with a private specialization of the existing frontend."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/memory936-native')
output.mkdir(exist_ok=True)
frontend = (experiment / 'memory_protection_frontend.h').read_text()
for before, after in [('0x93400000', '0x93600000'), ('0x802180f0', '0x802181d0'),
        ('0x802185a8', '0x802185c4'), ('0x802181c0', '0x802182a0')]:
    assert before in frontend
    frontend = frontend.replace(before, after)
(output / 'memory_protection_frontend.h').write_text(frontend)
host = (experiment / 'memory_protection_host.cpp').read_text().replace('0x93400000', '0x93600000')
(output / 'memory936_host.cpp').write_text(host)
parent = experiment / 'build_memory_protection_native.py'
body = parent.read_text().replace("output = private / 'memory-protection-native'", "output = private / 'memory936-native'")
body = body.replace('verify_memory_protection_dolphin.py', 'verify_memory936_dolphin.py')
body = body.replace('0x802180f0', '0x802181d0').replace('0x802181c0', '0x802182a0')
body = body.replace("str(experiment / 'memory_protection_frontend.h')", "str(output / 'memory_protection_frontend.h')")
body = body.replace("'-I', str(runtime / 'include')", "'-I', str(experiment), '-I', str(runtime / 'include')")
body = body.replace("(experiment / 'memory_protection_host.cpp').read_text()", "(output / 'memory936_host.cpp').read_text()")
body = body.replace("'sourceHashes': {str(path): sha(path) for path in sources}",
    "'sourceHashes': {str(path): sha(path) for path in sources + [output / 'memory_protection_frontend.h', output / 'memory936_host.cpp']}")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = output / 'build.json'
report = json.loads(path.read_text())
report['parentBuilderSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Private specialization of existing frontend, not a parallel cache/BAT/runtime.',
    'Exact936profile and alternate181D0only; old934frontend unchanged.',
    'No firstframe or original OSInit boot acceptance from standalone function.']
path.write_text(json.dumps(report, indent=2) + '\n')

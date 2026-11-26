"""Reuse full original/native comparison and guard suite for the alternate profile."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'verify_memory_protection_native.py'
body = parent.read_text().replace("output = private / 'memory-protection-native'", "output = private / 'memory936-native'")
body = body.replace('verify_memory_protection_dolphin.py', 'verify_memory936_dolphin.py')
body = body.replace('build_memory_protection_native.py', 'build_memory936_native.py')
body = body.replace('dolphin-memory-protection', 'dolphin-memory936')
body = body.replace('MEMORY_PROTECTION_SELECTED_REAL_MODE_BAT_GHIDRA214_856_PASS', 'MEMORY936_SELECTED_REAL_MODE_BAT_GHIDRA214_856_PASS')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/memory936-native')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert build['parentBuilderSha256'] == sha(experiment / 'build_memory_protection_native.py')
expected = (experiment / 'memory_protection_frontend.h').read_text()
for before, after in [('0x93400000', '0x93600000'), ('0x802180f0', '0x802181d0'),
        ('0x802185a8', '0x802185c4'), ('0x802181c0', '0x802182a0')]:
    expected = expected.replace(before, after)
assert (output / 'memory_protection_frontend.h').read_text() == expected
assert (output / 'memory936_host.cpp').read_text() == (experiment / 'memory_protection_host.cpp').read_text().replace('0x93400000', '0x93600000')
path = output / 'comparison.json'
report = json.loads(path.read_text())
report['result'] = 'WHOLE_COMPILED_MEMORY936_16_SCALARS_BAT_TABLE_QUEUE_MATCH'
report['parentVerifierSha256'] = sha(parent)
report['limits'] = build['limits'] + report['limits']
path.write_text(json.dumps(report, indent=2) + '\n')

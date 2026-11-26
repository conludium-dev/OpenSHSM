"""Extend the verified input test through the same manager; no guest/menu state edits."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-test-profile'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-test-ab/build.json'
parent = json.loads(parent_path.read_text())
for path, expected in {**parent['dependencies'], **parent['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
original = root / 'window-test-ab/main.cpp'
assert sha(original) == parent['sourceSha256']
text = original.read_text()
old_include = '#include "stock_test_ab_source.h"'
old_call = 'openshsm::experiment::install_test_ab_source('
assert text.count(old_include) == 1 and text.count(old_call) == 1
text = text.replace(old_include, '#include "stock_test_profile_source.h"').replace(
    old_call, 'openshsm::experiment::install_test_profile_source(')
source, obj = output / 'main.cpp', output / 'main.cpp.o'
source.write_text(text)
arguments = parent['arguments']
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
command = list(parent['linkCommand'])
command[command.index(str(original.with_suffix('.cpp.o')))] = str(obj)
exe = output / 'OpenSHSMStockTestProfile'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
(output / 'build.json').write_text(json.dumps({'result': 'PRIVATE_PROFILE_SOURCE_BUILT_LIVE_UNVERIFIED',
    'parentBuildSha256': sha(parent_path), 'sourceSha256': sha(source), 'objectSha256': sha(obj),
    'executableSha256': sha(exe), 'archiveSha256': parent['archiveSha256'], 'linkCommand': command,
    'arguments': arguments, 'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(),
        public / 'stock_test_profile_source.h', public / 'stock_test_ab_source.h',
        root / 'input-snapshot-research/include/input/input_manager.h']},
    'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).suffix == '.o'},
    'limits': ['Opt-in primary virtual source:750ms A+B then separate750ms A; no OS input/focus.',
        'Main object only, original menus/SDK bridge/75guests/runtime retained; no persistence/controller claim.']}, indent=2) + '\n')
print('PRIVATE_PROFILE_SOURCE_BUILT_LIVE_UNVERIFIED')

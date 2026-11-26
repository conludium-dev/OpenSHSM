"""Opt-in source through existing InputManager; no OS input or original menu-state substitution."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-test-ab'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base_path = root / 'headless-texture-eviction/build.json'
base = json.loads(base_path.read_text())
for path, expected in {**base['dependencies'], **base['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
command = list(base['linkCommand'])
old = next(Path(arg) for arg in command if Path(arg).name == 'main.cpp.o')
original = old.with_suffix('')
parent = json.loads((root / 'headless-tev-banks/build.json').read_text())
assert sha(original) == parent['mainSourceSha256']
marker = '  const char *headless_env = std::getenv("NWII_HEADLESS");'
text = original.read_text()
assert text.count(marker) == 1
text = '#include "stock_test_ab_source.h"\n' + text.replace(marker,
    '  openshsm::experiment::install_test_ab_source(nwii::runtime::input::InputManager::get());\n' + marker)
source, obj = output / 'main.cpp', output / 'main.cpp.o'
source.write_text(text)
record = next(row for row in json.loads((root / 'window-quantization/build.json').read_text())['compiled'] if row['source'] == 'main.cpp')
arguments = ['-I', str(root / 'input-snapshot-research/include'), '-I', str(root / 'headless-tev-banks/include'), *record['arguments']]
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
command[command.index(str(old))] = str(obj)
exe = output / 'OpenSHSMStockTestAB'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
(output / 'build.json').write_text(json.dumps({'result': 'PRIVATE_AB_SOURCE_BUILT_LIVE_UNVERIFIED',
    'baseBuildSha256': sha(base_path), 'sourceSha256': sha(source), 'objectSha256': sha(obj),
    'executableSha256': sha(exe), 'archiveSha256': base['archiveSha256'], 'linkCommand': command,
    'arguments': arguments, 'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(),
        public / 'stock_test_ab_source.h', root / 'input-snapshot-research/include/input/input_manager.h']},
    'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).suffix == '.o'},
    'limits': ['Opt-in private test source, primary virtual Wiimote/Nunchuk, exactly one750ms A+B pulse.',
        'Existing manager snapshots/SDK bridge consumed normally; no OS events, focus, game state forcing, device support claim.',
        'Main object only changed, all75guests/runtime/graphics/PSQ/FS/SC retained; no public launcher/release changes.']}, indent=2) + '\n')
print('PRIVATE_AB_SOURCE_BUILT_LIVE_UNVERIFIED')

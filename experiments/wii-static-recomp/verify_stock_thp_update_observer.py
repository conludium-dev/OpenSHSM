"""Read-only helper fixture, not original movie update execution."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-movie-update'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
source = Path('experiments/wii-static-recomp/stock_thp_update_contract.cpp').resolve()
obj, exe = output / 'contract.cpp.o', output / 'observer-contract'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *build['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=60)
(output / 'contract-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
command = list(build['linkCommand'])
full = root / 'window-quantization'
command[command.index(str(full / 'main.cpp.o'))] = str(full / 'contract-entry.cpp.o')
command.insert(1, str(obj))
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=60)
capture = output / 'component-movie-update.jsonl'
assert not capture.exists()
env = {key: value for key, value in os.environ.items() if not key.startswith(('SHSM_', 'NWII_'))}
env['NWII_THPDUMP'] = str(output / 'component')
result = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=20)
(output / 'contract.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
rows = [json.loads(line) for line in capture.read_text().splitlines()]
assert [row['pc'] for row in rows] == [0x8009B72C, 0x8009B750, 0x8009B760, 0x8009B770]
assert all(row['candidate'] == 0x80604000 and row['active'] == 0x80603000 and row['activeValid'] for row in rows)
(output / 'component.json').write_text(json.dumps({'result': 'MOVIE_UPDATE_HELPER_COMPONENT_PASS',
    'events': 4, 'buildSha256': sha(output / 'build.json'), 'sourceSha256': sha(source),
    'objectSha256': sha(obj), 'executableSha256': sha(exe), 'captureSha256': sha(capture),
    'logSha256': sha(output / 'contract.log'),
    'limits': ['Selected state/RAM preservation and synthetic four-point serialization; original update/IRQ/fullCR semantics not exercised.']}, indent=2) + '\n')
print('MOVIE_UPDATE_HELPER_COMPONENT_PASS')

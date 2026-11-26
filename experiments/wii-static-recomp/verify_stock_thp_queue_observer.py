"""Verify bounded queue metadata helper on the linked current CPU ABI; not original queue execution."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-movie-queues'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
source = Path('experiments/wii-static-recomp/stock_thp_queue_contract.cpp').resolve()
obj, exe = output / 'contract.cpp.o', output / 'observer-contract'
subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *build['arguments'],
    '-c', str(source), '-o', str(obj)], check=True, capture_output=True, timeout=60)
command = list(build['linkCommand'])
full = root / 'window-quantization'
command[command.index(str(full / 'main.cpp.o'))] = str(full / 'contract-entry.cpp.o')
command.insert(1, str(obj))
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=60)
capture = output / 'component-movie-queues.jsonl'
assert not capture.exists()
env = {key: value for key, value in os.environ.items() if not key.startswith(('SHSM_', 'NWII_'))}
env['NWII_THPDUMP'] = str(output / 'component')
result = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=20)
(output / 'contract.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
rows = [json.loads(line) for line in capture.read_text().splitlines()]
assert len(rows) == 2 and [row['function'] for row in rows] == [0x80217D30, 0x80217E00]
for row in rows:
    assert row['fieldsValid'] and row['headValid'] and row['head'] == 0x80603000
    assert (row['capacity'], row['first'], row['count']) == (4, 1, 2)
    assert row['headHex'] == row['argumentHex'] == '00' * 16
(output / 'component.json').write_text(json.dumps({'result': 'MOVIE_QUEUE_HELPER_COMPONENT_PASS',
    'events': 2, 'sourceSha256': sha(source), 'objectSha256': sha(obj), 'executableSha256': sha(exe),
    'captureSha256': sha(capture), 'buildSha256': sha(output / 'build.json'),
    'logSha256': sha(output / 'contract.log'), 'limits': ['Selected state/RAM preservation and header parsing only, not original send/receive/thread/IRQ execution.']}, indent=2) + '\n')
print('MOVIE_QUEUE_HELPER_COMPONENT_PASS')

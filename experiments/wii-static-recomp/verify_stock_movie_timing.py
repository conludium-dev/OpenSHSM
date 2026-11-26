"""Validate diagnostic cap/nonmutation, separate from original behavioral acceptance."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'headless-movie-timing'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base_path = output / 'build.json'
base = json.loads(base_path.read_text())
for path, expected in {**base['dependencies'], **base['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
archive = next(Path(arg) for arg in base['linkCommand'] if Path(arg).name == 'libnwiiruntime.a')
assert sha(archive) == base['archiveSha256']
record = next(row for row in json.loads((root / 'window-quantization/build.json').read_text())['compiled'] if row['source'] == 'ios.cpp')
source, obj = public / 'stock_movie_timing_probe.cpp', output / 'probe.cpp.o'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'probe-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2000:]
command = list(base['linkCommand'])
command[command.index(str(root / 'headless-tev-banks/main.cpp.o'))] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
command.insert(1, str(obj))
exe = output / 'timing-probe'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
descriptor, name = tempfile.mkstemp(prefix='component-', suffix='.jsonl', dir=output)
os.close(descriptor)
capture = Path(name)
env = {key: value for key, value in os.environ.items() if key != 'NWII_MOVIE_TIMING'}
off = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=30)
assert off.returncode == 0 and capture.stat().st_size == 0
on = subprocess.run([str(exe)], env=dict(env, NWII_MOVIE_TIMING=str(capture)), capture_output=True, text=True, timeout=30)
assert on.returncode == 0, on.stderr
rows = [json.loads(line) for line in capture.read_text().splitlines()]
assert len(rows) == 4096
assert all(row['serial'] == i and row['thread'] == 0x80568000 and row['owner'] == 0x80569000 for i, row in enumerate(rows))
assert all(rows[i]['hostUs'] <= rows[i + 1]['hostUs'] for i in range(len(rows) - 1))
(output / 'component-verification.json').write_text(json.dumps({'result': 'MOVIE_TIMING_COMPONENT_PASS4096_OFF_ON',
    'buildSha256': sha(base_path), 'probeSourceSha256': sha(source), 'executableSha256': sha(exe),
    'capture': str(capture), 'captureSha256': sha(capture), 'verifierSha256': sha(Path(__file__).resolve()),
    'limits': ['Synthetic populated state; no guest RAM/GPR/FP/MSR changes, off/on and4096cap.',
        'Not live video, original decoder/queue behavior or GPU/FPS acceptance.']}, indent=2) + '\n')
print('MOVIE_TIMING_COMPONENT_PASS4096_OFF_ON')

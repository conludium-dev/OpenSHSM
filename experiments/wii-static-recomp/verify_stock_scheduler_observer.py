"""Check bounded diagnostic RAM reads, record caps and cycle handling."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'headless-scheduler-observe'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base_path = output / 'build.json'
base = json.loads(base_path.read_text())
for path, expected in base['dependencies'].items():
    assert sha(Path(path)) == expected
record = next(row for row in json.loads((root / 'window-quantization/build.json').read_text())['compiled'] if row['source'] == 'ios.cpp')
source, obj = public / 'stock_scheduler_observation_probe.cpp', output / 'probe.cpp.o'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'probe-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2000:]
command = list(base['linkCommand'])
command[command.index(str(root / 'headless-tev-banks/main.cpp.o'))] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
command.insert(1, str(obj))
exe = output / 'scheduler-probe'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
prefix = output / 'component'
capture = Path(str(prefix) + '-scheduler.jsonl')
assert not capture.exists(), 'Refuse to append to older component evidence'
env = dict(os.environ, NWII_SCHED_OBSERVE=str(prefix))
result = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=30)
(output / 'probe.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
rows = [json.loads(line) for line in capture.read_text().splitlines()]
assert len(rows) == 24 and sum(row['idle'] for row in rows) == 16
assert all(len(row['threads']) == 1 and row['threads'][0]['word2CC'] == 1 for row in rows)
assert all(len(row['runQueues']) == 64 and row['runBits'] == 0 for row in rows)
(output / 'component-verification.json').write_text(json.dumps({'result': 'SCHEDULER_OBSERVER_COMPONENT_PASS24',
    'buildSha256': sha(base_path), 'executableSha256': sha(exe), 'captureSha256': sha(capture),
    'probeSourceSha256': sha(source), 'verifierSha256': sha(Path(__file__).resolve()),
    'limits': ['Synthetic RAM context,8normal/16idle caps,cyclebounded list,valid-bank ends/alias/invalidspan refusal,guest RAM/GPR unchanged.',
        'Not original scheduler behavior, real thread eligibility or live stall resolution proof.']}, indent=2) + '\n')
print('SCHEDULER_OBSERVER_COMPONENT_PASS24')

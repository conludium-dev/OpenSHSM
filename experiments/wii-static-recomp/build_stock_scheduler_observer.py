"""Read-only extension of the existing bounded scheduler diagnostic seam."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'headless-scheduler-observe'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base_path = root / 'headless-observer-env-cache/build.json'
base = json.loads(base_path.read_text())
for path, expected in base['dependencies'].items():
    assert sha(Path(path)) == expected
for path, expected in base['retainedLinkInputs'].items():
    assert sha(Path(path)) == expected
original = root / 'headless-observer-env-cache/ios.cpp'
assert sha(original) == base['iosSourceSha256']
text = original.read_text()
marker = '      if ((dcount++ % 500) == 0) {'
assert text.count(marker) == 1
text = '#include "stock_scheduler_observation.h"\n' + text.replace(marker,
    marker + '\n          stock_scheduler_observation::observe(ctx);')
source, obj = output / 'ios.cpp', output / 'ios.cpp.o'
source.write_text(text)
record = next(row for row in json.loads((root / 'window-quantization/build.json').read_text())['compiled'] if row['source'] == 'ios.cpp')
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
command = list(base['linkCommand'])
old = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
assert sha(old) == base['archiveSha256']
archive = output / 'libnwiiruntime.a'
shutil.copy2(old, archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], capture_output=True, check=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], capture_output=True, check=True)
retained = {}
for member in subprocess.check_output(['/usr/bin/ar', '-t', str(old)], text=True).splitlines():
    if member.startswith('__') or member == 'ios.cpp.o':
        continue
    data = subprocess.check_output(['/usr/bin/ar', '-p', str(old), member])
    assert data == subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    retained[member] = hashlib.sha256(data).hexdigest()
command[command.index(str(old))] = str(archive)
exe = output / 'OpenSHSMStockSchedulerObserve'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=180)
(output / 'build.json').write_text(json.dumps({'result': 'SCHEDULER_READ_ONLY_OBSERVER_BUILT_EXECUTION_UNVERIFIED',
    'baseBuildSha256': sha(base_path), 'originalSourceSha256': sha(original), 'sourceSha256': sha(source), 'objectSha256': sha(obj),
    'archiveSha256': sha(archive), 'executableSha256': sha(exe), 'linkCommand': command, 'retainedRuntimeMembers': retained,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), public / 'stock_scheduler_observation.h']},
    'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).suffix == '.o'},
    'limits': ['Existing scheduler summary cadence,8normal/16idle records and24bounded active threads; read-only RAM snapshots.',
        'Raw2CC/D8 fields not yet claimed as verified SHSM suspend/FPU-owner semantics.',
        'No queue/ready/MSR/FPU changes, callback forcing or gameplay/performance acceptance.']}, indent=2) + '\n')
print('SCHEDULER_READ_ONLY_OBSERVER_BUILT_EXECUTION_UNVERIFIED')

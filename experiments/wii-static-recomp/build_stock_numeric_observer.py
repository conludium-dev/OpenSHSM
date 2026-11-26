"""Replace two diagnostic host objects on the fully rebuilt locked-cache ABI."""
from pathlib import Path
import hashlib
import json
import shlex
import shutil
import subprocess
from stock_numeric_observation import adapt_calls, adapt_contexts
from stock_thp_observation import adapt_thp_calls
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--thp', action='store_true')
args = parser.parse_args()

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base = root / 'window-locked-cache'
output = root / ('window-lc-thp' if args.thp else 'window-lc-numeric')
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((base / 'build.json').read_text())
assert sha(base / 'OpenSHSMStockLockedCache') == build['executableSha256']
objects = []
adapters = [('os_hle_stubs.cpp', adapt_thp_calls)] if args.thp else [('os_hle_stubs.cpp', adapt_calls), ('ios.cpp', adapt_contexts)]
for name, adapter in adapters:
    item = next(item for item in build['compiled'] if item['source'] == name)
    original = base / name
    assert sha(original) == item['sourceSha256']
    source = output / name
    source.write_text(adapter(original.read_text()))
    obj = output / (name + '.o')
    compiler = '/Library/Developer/CommandLineTools/usr/bin/c++'
    result = subprocess.run([compiler, *item['arguments'], '-c', str(source), '-o', str(obj)],
        capture_output=True, text=True, timeout=120)
    (output / (name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-4000:]
    objects.append(obj)
archive = output / 'libnwiiruntime.a'
shutil.copy2(base / 'libnwiiruntime.a', archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), *map(str, objects)], check=True, capture_output=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
retained_runtime = {}
for member in subprocess.check_output(['/usr/bin/ar', '-t', str(base / 'libnwiiruntime.a')], text=True).splitlines():
    if member.startswith('__.SYMDEF') or member in {obj.name for obj in objects}:
        continue
    old = subprocess.check_output(['/usr/bin/ar', '-p', str(base / 'libnwiiruntime.a'), member])
    assert old == subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member]), member
    retained_runtime[member] = hashlib.sha256(old).hexdigest()
command = shlex.split((root / 'export/build/CMakeFiles/OpenSHSMStockBaseline.dir/link.txt').read_text())
retained = {}
for index in range(75):
    name = f'output_{index}.cpp.o'
    command[command.index('CMakeFiles/OpenSHSMStockBaseline.dir/' + name)] = str(base / name)
    retained[str(base / name)] = sha(base / name)
for original, name in [('CMakeFiles/OpenSHSMStockBaseline.dir/main_output.cpp.o', 'main_output.cpp.o'),
    ('CMakeFiles/OpenSHSMStockBaseline.dir/nWiiRuntime/src/core/main.cpp.o', 'main.cpp.o')]:
    command[command.index(original)] = str(base / name)
    retained[str(base / name)] = sha(base / name)
command[command.index('nWiiRuntime/libnwiiruntime.a')] = str(archive)
exe = output / ('OpenSHSMStockTHPObserver' if args.thp else 'OpenSHSMStockNumericObserver')
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=120)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-4000:]
(output / 'build.json').write_text(json.dumps({'result': 'READ_ONLY_NUMERIC_STATE_OBSERVER',
    'retainedObjects': retained, 'retainedRuntimeMembers': retained_runtime,
    'baseBuildSha256': sha(base / 'build.json'), 'executableSha256': sha(exe),
    'sources': {obj.stem: {'sourceSha256': sha(obj.with_suffix('')), 'objectSha256': sha(obj)} for obj in objects},
    'archiveSha256': sha(archive), 'limits': ['Read-only bounded state snapshots; no guest input/state/timing changes.',
        'Missing sampled event does not prove absent execution; logging can affect timing.']}, indent=2) + '\n')
print('Built numeric observer; all77ABI-correct guest/entry/dispatcher objects retained', flush=True)

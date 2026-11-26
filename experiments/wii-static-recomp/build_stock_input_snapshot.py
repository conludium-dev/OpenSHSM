"""Compile a private InputManager snapshot component and prove retained archive members unchanged."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
from stock_input_snapshot_patch import adapt

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'input-snapshot-research'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
original_header = root / 'export/nWiiRuntime/include/input/input_manager.h'
original_source = root / 'export/nWiiRuntime/src/input/input_manager.cpp'
header, source = adapt(original_header.read_text(), original_source.read_text())
header_path = output / 'include/input/input_manager.h'
header_path.parent.mkdir(parents=True, exist_ok=True)
header_path.write_text(header)
source_path = output / 'input_manager.cpp'
source_path.write_text(source)
build_path = root / 'window-legacy-context/build.json'
command = list(json.loads(build_path.read_text())['linkCommand'])
full = root / 'window-quantization'
arguments = next(row['arguments'] for row in json.loads((full / 'build.json').read_text())['compiled']
    if row['source'] == 'main_output.cpp')
arguments = ['-I', str(output / 'include'), *arguments]
obj = output / 'input_manager.cpp.o'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments, '-c', str(source_path), '-o', str(obj)],
    capture_output=True, text=True, timeout=60)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
archive_old = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
archive = output / 'libnwiiruntime.a'
shutil.copy2(archive_old, archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], check=True, capture_output=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
retained = {}
members = subprocess.check_output(['/usr/bin/ar', '-t', str(archive_old)], text=True).splitlines()
for member in members:
    if member == obj.name or member.startswith('__'):
        continue
    before = subprocess.check_output(['/usr/bin/ar', '-p', str(archive_old), member])
    after = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    assert before == after
    retained[member] = hashlib.sha256(before).hexdigest()
probe_source = Path('experiments/wii-static-recomp/stock_input_snapshot_probe.cpp').resolve()
probe_obj = output / 'probe.cpp.o'
subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments, '-c', str(probe_source), '-o', str(probe_obj)],
    capture_output=True, check=True, timeout=60)
command[command.index(str(full / 'main.cpp.o'))] = str(full / 'contract-entry.cpp.o')
command[command.index(str(archive_old))] = str(archive)
command.insert(1, str(probe_obj))
exe = output / 'input-snapshot-probe'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=60)
runs = []
for index in range(3):
    result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=20)
    path = output / f'probe-{index}.log'
    path.write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and 'INPUT_SNAPSHOT_PASS' in result.stdout, result.stdout + result.stderr
    runs.append({'logSha256': sha(path), 'output': result.stdout.strip()})
regressions = {}
for name, expected in [('stock_host_input_probe', 'LINKED_HOST_INPUT_PROVIDER_PRESENT'),
        ('stock_input_connection_probe', 'PRIMARY_CONNECTION_ADAPTER_PASS 7 polls/4 registration-context refusals')]:
    regression_source = Path('experiments/wii-static-recomp') / (name + '.cpp')
    regression_obj = output / (name + '.cpp.o')
    subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments, '-c', str(regression_source.resolve()),
        '-o', str(regression_obj)], capture_output=True, check=True, timeout=60)
    regression_command = list(command)
    regression_command[regression_command.index(str(probe_obj))] = str(regression_obj)
    regression_exe = output / name
    regression_command[regression_command.index('-o') + 1] = str(regression_exe)
    subprocess.run(regression_command, cwd=root / 'export/build', capture_output=True, check=True, timeout=60)
    result = subprocess.run([str(regression_exe)], capture_output=True, text=True, timeout=20)
    log = output / (name + '.log')
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and expected in result.stdout
    regressions[name] = {'sourceSha256': sha(regression_source), 'objectSha256': sha(regression_obj),
        'executableSha256': sha(regression_exe), 'logSha256': sha(log), 'result': expected}
(output / 'build.json').write_text(json.dumps({'result': 'INPUT_SNAPSHOT_COMPONENT_PASS',
    'recipeSha256': sha(Path(__file__)), 'patchSha256': sha(Path('experiments/wii-static-recomp/stock_input_snapshot_patch.py')),
    'baseBuildSha256': sha(build_path), 'originalHeaderSha256': sha(original_header), 'originalSourceSha256': sha(original_source),
    'headerSha256': sha(header_path), 'sourceSha256': sha(source_path), 'objectSha256': sha(obj), 'archiveSha256': sha(archive),
    'probeSourceSha256': sha(probe_source), 'probeObjectSha256': sha(probe_obj), 'executableSha256': sha(exe),
    'retainedRuntimeMembers': retained, 'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file()
        and Path(arg).suffix in ('.o', '.a') and arg not in [str(probe_obj), str(archive)]},
    'arguments': arguments, 'linkCommand': command, 'runs': runs, 'regressions': regressions,
    'limits': ['Actual InputManager with controlled IInputSource; no hardware or SDL input injected.',
        'PC adaptation queue keeps16 pending snapshots/channel, drops oldest with a counter on overflow; not original Wii timing/queue equivalence.',
        'Existing input storage/provider registry retained; one archive member replaced privately, no live game binding.',
        'Finite mutex/coherence stress tests, not a full thread sanitizer proof.']}, indent=2) + '\n')
print('INPUT_SNAPSHOT_COMPONENT_PASS 3 runs; retained runtime members', len(retained))

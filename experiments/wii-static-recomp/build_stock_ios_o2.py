"""Compile identical current unprofiled IOS source with O2 only; preserve every other runtime/guest object."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-ios-o2'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-movie-input/build.json'
parent = json.loads(parent_path.read_text())
for path, digest in {**parent['dependencies'], **parent['retainedInputs']}.items():
    assert sha(Path(path)) == digest
prepared_path = root / 'callback-profile-component/verification.json'
prepared = json.loads(prepared_path.read_text())
original = root / 'headless-scheduler-observe/ios.cpp'
assert sha(original) == prepared['originalSourceSha256']
flags = list(prepared['arguments'])
assert not any(arg.startswith('-O') for arg in flags)
arguments = flags + ['-O2']
source, obj = output / 'ios.cpp', output / 'ios.cpp.o'
source.write_bytes(original.read_bytes())
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=90)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2500:]
command = list(parent['linkCommand'])
old_archive = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
assert sha(old_archive) == prepared['archiveSha256']
assert hashlib.sha256(subprocess.check_output(['/usr/bin/ar', '-p', str(old_archive), 'ios.cpp.o'])).hexdigest() == prepared['originalObjectSha256']
archive = output / 'libnwiiruntime.a'
shutil.copyfile(old_archive, archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], capture_output=True, check=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], capture_output=True, check=True)
members = {}
for member in subprocess.check_output(['/usr/bin/ar', '-t', str(old_archive)], text=True).splitlines():
    if member.startswith('__'):
        continue
    before = subprocess.check_output(['/usr/bin/ar', '-p', str(old_archive), member])
    after = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    if member == 'ios.cpp.o':
        assert hashlib.sha256(after).hexdigest() == sha(obj)
    else:
        assert before == after
    members[member] = hashlib.sha256(after).hexdigest()
command[command.index(str(old_archive))] = str(archive)
cache = Path(tempfile.mkdtemp(prefix='openshsm-ios-o2-', dir='/private/tmp'))
exe = cache / 'OpenSHSMStockIOSO2'
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2500:]
inputs = {}
for arg in command:
    if Path(arg).suffix in ('.o', '.a') and arg != str(archive):
        path = (Path(arg) if Path(arg).is_absolute() else root / 'export/build' / arg).resolve()
        inputs[str(path)] = sha(path)
(output / 'build.json').write_text(json.dumps({
    'result': 'IDENTICAL_IOS_O2_BUILT_EXECUTION_UNVERIFIED', 'parentBuildSha256': sha(parent_path),
    'preparedComponentSha256': sha(prepared_path), 'originalSourcePath': str(original),
    'originalSourceSha256': sha(original), 'sourceSha256': sha(source), 'objectSha256': sha(obj),
    'originalArguments': flags, 'arguments': arguments, 'archiveSha256': sha(archive), 'members': members,
    'linkCommand': command, 'executablePath': str(exe), 'executableSha256': sha(exe), 'retainedInputs': inputs,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), original, source]},
    'limits': ['Identical unprofiled IOS source; O2 is sole added compiler option, no new observer counters.',
        'One archive member only; every other member/masterO0/all75guests/main/audio/clock/IRQ/waits retained.',
        'Existing movie input/timing diagnostics retained; large exe temporary Mac cache, no publication.',
        'Actual callback/frame/SC/resume/IRQ/live/visual/audio validation pending; no default promotion.']}, indent=2) + '\n')
print('IDENTICAL_IOS_O2_BUILT_EXECUTION_UNVERIFIED', exe)

"""Integrate the prepared IOS counter object with the existing movie observer; keep the large exe off Data."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-callback-profile'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-movie-input/build.json'
parent = json.loads(parent_path.read_text())
for path, digest in {**parent['dependencies'], **parent['retainedInputs']}.items():
    assert sha(Path(path)) == digest
prepared_path = root / 'callback-profile-component/verification.json'
prepared = json.loads(prepared_path.read_text())
ios_obj = prepared_path.parent / 'ios.cpp.o'
assert sha(ios_obj) == prepared['objectSha256']
assert sha(public / 'stock_callback_profile.h') == prepared['helperSha256']
command = list(parent['linkCommand'])
old_archive = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
assert sha(old_archive) == prepared['archiveSha256']
archive = output / 'libnwiiruntime.a'
shutil.copyfile(old_archive, archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(ios_obj)], capture_output=True, check=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], capture_output=True, check=True)
members = {}
for member in subprocess.check_output(['/usr/bin/ar', '-t', str(old_archive)], text=True).splitlines():
    if member.startswith('__'):
        continue
    before = subprocess.check_output(['/usr/bin/ar', '-p', str(old_archive), member])
    after = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    if member == 'ios.cpp.o':
        assert hashlib.sha256(after).hexdigest() == prepared['objectSha256']
    else:
        assert before == after
    members[member] = hashlib.sha256(after).hexdigest()
command[command.index(str(old_archive))] = str(archive)
original_header = root / 'window-movie-input/stock_movie_timing.h'
text = original_header.read_text()
patches = [('#include <time.h>', '#include <time.h>\nextern "C" void stock_callback_profile_snapshot(uint64_t*);'),
    ('    timespec cpu_time{};', '    uint64_t profile[10]{};\n    stock_callback_profile_snapshot(profile);\n    timespec cpu_time{};'),
    ('\\"r6\\":%u}\\n', '\\"r6\\":%u,\\"callbackProfile\\":[%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu]}\\n'),
    ('ctx.gpr[3], ctx.gpr[4], ctx.gpr[5], ctx.gpr[6]);',
     'ctx.gpr[3], ctx.gpr[4], ctx.gpr[5], ctx.gpr[6],\n' +
     '        ' + ', '.join(f'(unsigned long long)profile[{i}]' for i in range(10)) + ');')]
for before, after in patches:
    assert text.count(before) == 1
    text = text.replace(before, after, 1)
header = output / 'stock_movie_timing.h'
header.write_text(text)
for name in ('constant_fp_guard.h', 'stock_movie_input.h'):
    (output / name).write_bytes((root / 'window-movie-input' / name).read_bytes())
changes = {}
for unit in (11, 37):
    old = next(Path(arg) for arg in command if Path(arg).name == f'output_{unit}.cpp.o')
    original = old.with_suffix('')
    source, obj = output / original.name, output / old.name
    source.write_bytes(original.read_bytes())
    flags = parent['changes'][str(unit)]['arguments']
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *flags,
        '-I', str(original.parent), '-I', str(root / 'headless-psq-scale'), '-I', str(root / 'window-movie-dma'),
        '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
    (output / f'compile-{unit}.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-2500:]
    command[command.index(str(old))] = str(obj)
    changes[str(unit)] = {'originalPath': str(original), 'originalSha256': sha(original),
        'sourceSha256': sha(source), 'objectSha256': sha(obj), 'arguments': flags}
cache = Path(tempfile.mkdtemp(prefix='openshsm-callback-live-', dir='/private/tmp'))
exe = cache / 'OpenSHSMStockCallbackProfile'
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2500:]
inputs = {}
for arg in command:
    if Path(arg).suffix in ('.o', '.a'):
        path = (Path(arg) if Path(arg).is_absolute() else root / 'export/build' / arg).resolve()
        inputs[str(path)] = sha(path)
(output / 'build.json').write_text(json.dumps({
    'result': 'CALLBACK_PROFILE_INTEGRATED_LIVE_UNVERIFIED', 'parentBuildSha256': sha(parent_path),
    'preparedComponentSha256': sha(prepared_path), 'archiveSha256': sha(archive), 'members': members,
    'headerPatches': patches, 'changes': changes, 'counterOrder': prepared['counterOrder'],
    'executablePath': str(exe), 'executableSha256': sha(exe), 'linkCommand': command, 'retainedInputs': inputs,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), original_header, header,
        public / 'stock_callback_profile.h', output / 'constant_fp_guard.h', output / 'stock_movie_input.h']},
    'limits': ['Only IOS observer wrapper/counter and existing movie header extended; guest11/37 source identical.',
        'All other archive members/master/73guests/main/audio/clock retained.',
        'Counters sampled on same CPU thread; nonlocal sample exits missing intentionally, no RAII.',
        'Large executable is temporary Mac cache; manifests/resources/project remain Data, rebuild if cache expires.',
        'Full-frame/actual callback regression and GUI profile pending; no default promotion.']}, indent=2) + '\n')
print('CALLBACK_PROFILE_INTEGRATED_LIVE_UNVERIFIED', exe)

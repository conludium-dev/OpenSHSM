"""Reuse proven lightweight counters on current IOSO2 and delayed movie observer, retaining current runtime."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-callback-o2-profile'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-dispatch-o2/build.json'
parent = json.loads(parent_path.read_text())
parent_component_path = parent_path.parent / 'component-verification.json'
parent_component = json.loads(parent_component_path.read_text())
assert parent_component['result'] == 'DISPATCH_O2_ROUTES_CALLBACK4_SDK7_SC3_LATE18_EQUAL'
assert parent_component['buildSha256'] == sha(parent_path)
for path, digest in {**parent['dependencies'], **parent['retainedInputs']}.items():
    assert sha(Path(path)) == digest
ios_path = root / 'window-ios-o2/build.json'
ios = json.loads(ios_path.read_text())
original = root / 'window-ios-o2/ios.cpp'
assert sha(original) == ios['sourceSha256']
prepared_path = root / 'callback-profile-component/verification.json'
prepared = json.loads(prepared_path.read_text())
prepared_source = prepared_path.parent / 'ios.cpp'
assert sha(prepared_source) == prepared['sourceSha256']
assert sha(public / 'stock_callback_profile.h') == prepared['helperSha256']
restored = prepared_source.read_text().replace('#include "stock_callback_profile.h"\n', '', 1)
assert restored.count(prepared['wrapper']) == 1
restored = restored.replace(prepared['wrapper'], '', 1)
for before, after in reversed(prepared['patches']):
    assert restored.count(after) == 1
    restored = restored.replace(after, before, 1)
assert restored == original.read_text()
cache = Path(tempfile.mkdtemp(prefix='openshsm-callback-o2-', dir='/private/tmp'))
source, obj = cache / 'ios.cpp', cache / 'ios.cpp.o'
source.write_bytes(prepared_source.read_bytes())
arguments = ios['arguments']
assert arguments == ios['originalArguments'] + ['-O2']
compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=90)
(output / 'ios-compile.log').write_text(compiled.stdout + compiled.stderr)
assert compiled.returncode == 0, compiled.stderr[-2500:]
command = list(parent['linkCommand'])
old_archive = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
assert hashlib.sha256(subprocess.check_output(['/usr/bin/ar', '-p', str(old_archive), 'ios.cpp.o'])).hexdigest() == ios['objectSha256']
archive = cache / 'libnwiiruntime.a'
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
original_header = root / 'window-movie-late/stock_movie_timing.h'
old_profile_path = root / 'window-callback-profile/build.json'
old_profile = json.loads(old_profile_path.read_text())
text = original_header.read_text()
for before, after in old_profile['headerPatches']:
    assert text.count(before) == 1
    text = text.replace(before, after, 1)
header = cache / 'stock_movie_timing.h'
header.write_text(text)
for name in ('constant_fp_guard.h', 'stock_movie_input.h', 'stock_movie_capture_gate.h'):
    (cache / name).write_bytes((root / 'window-movie-late' / name).read_bytes())
guest_flags = json.loads((root / 'window-movie-late/build.json').read_text())['changes']
changes = {}
for unit in (11, 37):
    old = next(Path(arg) for arg in command if Path(arg).name == f'output_{unit}.cpp.o')
    original_guest = old.with_suffix('')
    guest, guest_obj = cache / original_guest.name, cache / old.name
    guest.write_bytes(original_guest.read_bytes())
    flags = guest_flags[str(unit)]['arguments']
    compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *flags,
        '-I', str(original_guest.parent), '-I', str(root / 'headless-psq-scale'), '-I', str(root / 'window-movie-dma'),
        '-c', str(guest), '-o', str(guest_obj)], capture_output=True, text=True, timeout=180)
    (output / f'compile-{unit}.log').write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0, compiled.stderr[-2500:]
    command[command.index(str(old))] = str(guest_obj)
    changes[str(unit)] = {'originalPath': str(original_guest), 'originalSha256': sha(original_guest),
        'sourcePath': str(guest), 'sourceSha256': sha(guest), 'objectPath': str(guest_obj),
        'objectSha256': sha(guest_obj), 'arguments': flags}
exe = cache / 'OpenSHSMStockCallbackO2Profile'
command[command.index('-o') + 1] = str(exe)
linked = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(linked.stdout + linked.stderr)
assert linked.returncode == 0, linked.stderr[-2500:]
retained = {}
for arg in command:
    if Path(arg).suffix in ('.o', '.a') and arg not in [str(archive), *(change['objectPath'] for change in changes.values())]:
        path = (Path(arg) if Path(arg).is_absolute() else root / 'export/build' / arg).resolve()
        retained[str(path)] = sha(path)
(output / 'build.json').write_text(json.dumps({
    'result': 'CURRENT_IOS_O2_LATE_CALLBACK_PROFILE_BUILT_UNVERIFIED',
    'parentBuildSha256': sha(parent_path), 'parentComponentSha256': sha(parent_component_path),
    'preparedComponentSha256': sha(prepared_path), 'oldProfileBuildSha256': sha(old_profile_path),
    'iosOriginalPath': str(original), 'iosSourcePath': str(source), 'iosSourceSha256': sha(source),
    'iosObjectPath': str(obj), 'iosObjectSha256': sha(obj), 'iosArguments': arguments,
    'headerOriginalPath': str(original_header), 'headerPath': str(header), 'headerPatches': old_profile['headerPatches'],
    'changes': changes, 'counterOrder': prepared['counterOrder'], 'members': members,
    'archivePath': str(archive), 'archiveSha256': sha(archive), 'linkCommand': command,
    'executablePath': str(exe), 'executableSha256': sha(exe), 'retainedInputs': retained,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), prepared_source, source,
        public / 'stock_callback_profile.h', original_header, header, *(cache / name for name in
        ('stock_movie_input.h', 'stock_movie_capture_gate.h', 'constant_fp_guard.h'))]},
    'limits': ['Existing trivial counter wrapper around same current IOS body compiled with SAME current O2 flags.',
        'Only IOS archive member and unchanged-source11/37/header observer extended; current master/exact helper/scheduler/texture/audio/IRQ/waits retained.',
        'Delayed70s/128packet16MiB/4096event limits retained; sampling one in1024, missing nonlocal returns not timed.',
        'All new large files temporary cache, no release/runtime promotion; actual nonlocal/frame/live profile pending.']}, indent=2) + '\n')
print('CURRENT_IOS_O2_LATE_CALLBACK_PROFILE_BUILT_UNVERIFIED', exe)

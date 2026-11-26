"""Skip only the pure DEC deadline query under masked EE; retain unconditional event advance."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-dec-ee-gate'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-dispatch-o2/build.json'
parent = json.loads(parent_path.read_text())
component_path = parent_path.parent / 'component-verification.json'
component = json.loads(component_path.read_text())
assert component['result'] == 'DISPATCH_O2_ROUTES_CALLBACK4_SDK7_SC3_LATE18_EQUAL'
assert component['buildSha256'] == sha(parent_path)
for path, digest in {**parent['dependencies'], **parent['retainedInputs']}.items():
    assert sha(Path(path)) == digest
ios_path = root / 'window-ios-o2/build.json'
ios = json.loads(ios_path.read_text())
original = root / 'window-ios-o2/ios.cpp'
assert sha(original) == ios['sourceSha256']
before = 'if (ctx.dec_expired() && (ctx.msr & 0x8000) && !ctx.in_callback) {'
after = 'if ((ctx.msr & 0x8000) && !ctx.in_callback && ctx.dec_expired()) {'
text = original.read_text()
assert text.count(before) == 1
assert text.index('EventScheduler::get().advance(ctx, ctx.read_timebase());') < text.index(before)
header = root / 'window-quantization/include/runtime/cpu_context.h'
assert 'return dec_irq_pending && (read_timebase() - dec_written_tb) >= dec_value;' in header.read_text()
cache = Path(tempfile.mkdtemp(prefix='openshsm-dec-ee-gate-', dir='/private/tmp'))
source, obj = cache / 'ios.cpp', cache / 'ios.cpp.o'
source.write_text(text.replace(before, after, 1))
assert source.read_text().replace(after, before, 1) == text
arguments = ios['arguments']
compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=90)
(output / 'compile.log').write_text(compiled.stdout + compiled.stderr)
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
    old = subprocess.check_output(['/usr/bin/ar', '-p', str(old_archive), member])
    new = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    if member == 'ios.cpp.o':
        assert hashlib.sha256(new).hexdigest() == sha(obj)
    else:
        assert old == new
    members[member] = hashlib.sha256(new).hexdigest()
command[command.index(str(old_archive))] = str(archive)
exe = cache / 'OpenSHSMStockDECEEGate'
command[command.index('-o') + 1] = str(exe)
linked = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(linked.stdout + linked.stderr)
assert linked.returncode == 0, linked.stderr[-2500:]
retained = {}
for arg in command:
    if Path(arg).suffix in ('.o', '.a') and arg != str(archive):
        path = (Path(arg) if Path(arg).is_absolute() else root / 'export/build' / arg).resolve()
        retained[str(path)] = sha(path)
(output / 'build.json').write_text(json.dumps({
    'result': 'PURE_DEC_DEADLINE_EE_GATE_BUILT_UNVERIFIED', 'parentBuildSha256': sha(parent_path),
    'parentComponentSha256': sha(component_path), 'iosBuildSha256': sha(ios_path),
    'originalSourcePath': str(original), 'sourcePath': str(source), 'sourceSha256': sha(source),
    'objectPath': str(obj), 'objectSha256': sha(obj), 'arguments': arguments, 'patch': [before, after],
    'archivePath': str(archive), 'archiveSha256': sha(archive), 'members': members,
    'linkCommand': command, 'executablePath': str(exe), 'executableSha256': sha(exe), 'retainedInputs': retained,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), original, source, header]},
    'limits': ['Only predicate evaluation order changed in existing native IOS adapter; no DEC pending/handler/rate change.',
        'Unconditional preceding event advance/timebase read retained, no audio/device deadline suppression.',
        'All other archive members/master/exact helper/75guests/renderer/audio/clock/waits retained; same current O2 flags.',
        'Native adaptation, not newly recovered Wii logic; masked/due/handler/nonlocal/frame/live proof pending.',
        'Large generated source/object/archive/executable explicitly temporary cache, small private report on Data.']}, indent=2) + '\n')
print('PURE_DEC_DEADLINE_EE_GATE_BUILT_UNVERIFIED', exe)

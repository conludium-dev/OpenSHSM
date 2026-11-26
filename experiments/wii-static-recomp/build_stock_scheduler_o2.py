"""Replace only the current ADMA deadline scheduler object with identical source compiled O2."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-scheduler-o2'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
proof_path = root / 'late-packet-replay/scheduler-provenance.json'
proof = json.loads(proof_path.read_text())
assert proof['result'] == 'CURRENT_ARCHIVE_SCHEDULER_OBJECT_DEFAULT_O0_PINNED'
parent_path = root / 'window-movie-late/build.json'
parent = json.loads(parent_path.read_text())
assert sha(parent_path) == proof['buildSha256']
for path, digest in {**parent['dependencies'], **parent['retainedInputs']}.items():
    assert sha(Path(path)) == digest
original = Path(proof['sourcePath'])
assert sha(original) == proof['sourceSha256']
cache = Path(tempfile.mkdtemp(prefix='openshsm-scheduler-o2-', dir='/private/tmp'))
source, obj = cache / 'event_scheduler.cpp', cache / 'event_scheduler.cpp.o'
source.write_bytes(original.read_bytes())
arguments = proof['compileFlags'] + ['-O2']
compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=60)
(output / 'compile.log').write_text(compiled.stdout + compiled.stderr)
assert compiled.returncode == 0, compiled.stderr[-2500:]
old_archive = Path(proof['archivePath'])
assert sha(old_archive) == proof['archiveSha256']
archive = cache / 'libnwiiruntime.a'
shutil.copyfile(old_archive, archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], capture_output=True, check=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], capture_output=True, check=True)
members = {}
for member in subprocess.check_output(['/usr/bin/ar', '-t', str(old_archive),], text=True).splitlines():
    if member.startswith('__'):
        continue
    before = subprocess.check_output(['/usr/bin/ar', '-p', str(old_archive), member])
    after = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    if member == 'event_scheduler.cpp.o':
        assert hashlib.sha256(before).hexdigest() == proof['objectSha256']
        assert hashlib.sha256(after).hexdigest() == sha(obj)
    else:
        assert before == after
    members[member] = hashlib.sha256(after).hexdigest()
command = list(parent['linkCommand'])
command[command.index(str(old_archive))] = str(archive)
exe = cache / 'OpenSHSMStockSchedulerO2'
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
    'result': 'IDENTICAL_CURRENT_SCHEDULER_O2_BUILT_UNVERIFIED', 'parentBuildSha256': sha(parent_path),
    'provenanceSha256': sha(proof_path), 'originalSourcePath': str(original), 'sourcePath': str(source),
    'sourceSha256': sha(source), 'objectPath': str(obj), 'objectSha256': sha(obj),
    'originalArguments': proof['compileFlags'], 'arguments': arguments, 'members': members,
    'archivePath': str(archive), 'archiveSha256': sha(archive), 'executablePath': str(exe),
    'executableSha256': sha(exe), 'linkCommand': command, 'retainedInputs': retained,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), original, source]},
    'limits': ['Byte-identical current ADMA deadline scheduler source/O2only; additive schedule_at preserved.',
        'All other archive members/master/all75guests/IOS/texture/main/audio/clock/IRQ/waits retained.',
        'Native host adapter, not recovered Wii implementation; contracts/frame/live proof pending.',
        'All large new source/object/archive/executable in explicit temporary cache, private manifest on Data.']}, indent=2) + '\n')
print('IDENTICAL_CURRENT_SCHEDULER_O2_BUILT_UNVERIFIED', exe)

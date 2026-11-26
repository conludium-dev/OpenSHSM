"""Link only the prepared diagnostic IOS member into current timer-only main."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-current-vi-timer/build.json'
parent = json.loads(parent_path.read_text())
proof_path = root / 'vi-timer-profile/verification.json'
proof = json.loads(proof_path.read_text())
assert proof['result'] == 'VI_TIMER_PROFILE_IOS_COMPILED_GATE32_ENABLED_DISABLED_EQUAL'
assert proof['parentBuildSha256'] == sha(root / 'window-dec-ee-gate/build.json')
for path, digest in {**parent['dependencies'], **parent['retainedInputs'], **proof['dependencies']}.items():
    assert sha(Path(path)) == digest
source, obj = Path(proof['preparedSourcePath']), Path(proof['runtimeObjectPath'])
assert sha(source) == proof['preparedSourceSha256']
assert sha(obj) == proof['runtimeObjectSha256']
original = Path(proof['originalSourcePath'])
assert sha(original) == proof['originalSourceSha256']
before, after = proof['patch']
assert source.read_text().removeprefix('#include "stock_vi_timer_profile.h"\n').replace(after, before, 1) == original.read_text()
cache = Path(tempfile.mkdtemp(prefix='openshsm-vi-profile-link-', dir='/private/tmp'))
command = list(parent['linkCommand'])
old_archive = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
dec = json.loads((root / 'window-dec-ee-gate/build.json').read_text())
assert sha(old_archive) == dec['archiveSha256']
archive = cache / 'libnwiiruntime.a'
shutil.copyfile(old_archive, archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], check=True, capture_output=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
members = {}
for member in subprocess.check_output(['/usr/bin/ar', '-t', str(old_archive)], text=True).splitlines():
    if member.startswith('__'):
        continue
    old = subprocess.check_output(['/usr/bin/ar', '-p', str(old_archive), member])
    new = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    assert (hashlib.sha256(new).hexdigest() == sha(obj)) if member == 'ios.cpp.o' else (old == new)
    members[member] = hashlib.sha256(new).hexdigest()
command[command.index(str(old_archive))] = str(archive)
exe = cache / 'OpenSHSMStockVITimerProfile'
command[command.index('-o') + 1] = str(exe)
output = root / 'window-vi-timer-profile'
output.mkdir(exist_ok=True)
linked = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(linked.stdout + linked.stderr)
assert linked.returncode == 0, linked.stderr[-2500:]
retained = {}
for arg in command:
    if Path(arg).suffix in ('.o', '.a') and arg != str(archive):
        path = (Path(arg) if Path(arg).is_absolute() else root / 'export/build' / arg).resolve()
        retained[str(path)] = sha(path)
(output / 'build.json').write_text(json.dumps({
    'result': 'EXISTING_VI_TIMER_PROFILE_LINKED_UNVERIFIED',
    'parentBuildSha256': sha(parent_path), 'preparationSha256': sha(proof_path),
    'sourcePath': str(source), 'sourceSha256': sha(source), 'originalSourcePath': str(original),
    'objectPath': str(obj), 'objectSha256': sha(obj), 'patch': proof['patch'],
    'arguments': dec['arguments'], 'archivePath': str(archive), 'archiveSha256': sha(archive),
    'members': members, 'linkCommand': command, 'executablePath': str(exe),
    'executableSha256': sha(exe), 'retainedInputs': retained,
    'dependencies': {**proof['dependencies'], str(Path(__file__).resolve()): sha(Path(__file__)),
        str(proof_path): sha(proof_path), str(source): sha(source), str(original): sha(original)},
    'limits': ['Only IOS archive member replaced; all other runtime/guest/main objects retained.',
        'Diagnostic opt-in observer, not a timing fix or default promotion; live counts pending.']}, indent=2) + '\n')
print('EXISTING_VI_TIMER_PROFILE_LINKED_UNVERIFIED', exe)

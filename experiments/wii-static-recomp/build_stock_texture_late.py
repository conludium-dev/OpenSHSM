"""Link only the prepared diagnostic texture member into the verified select parent."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-dispatch-select/build.json'
parent = json.loads(parent_path.read_text())
component_path = parent_path.parent / 'component-verification.json'
component = json.loads(component_path.read_text())
assert component['result'] == 'DISPATCH_SELECT_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_EQUAL'
assert component['buildSha256'] == sha(parent_path)
proof_path = root / 'texture-late-preparation/verification.json'
proof = json.loads(proof_path.read_text())
for path, digest in {**parent['dependencies'], **parent['retainedInputs'], **proof['dependencies']}.items():
    assert sha(Path(path)) == digest
source, obj = Path(proof['preparedSourcePath']), Path(proof['objectPath'])
header = Path(proof['preparedHeaderPath'])
assert sha(source) == proof['preparedSourceSha256'] and sha(obj) == proof['objectSha256']
assert sha(header) == proof['preparedHeaderSha256']
original = root / 'headless-texture-eviction/texture_cache_gl.cpp'
assert source.read_text().replace(proof['sourcePatch'][1], proof['sourcePatch'][0], 1) == original.read_text()
cache = Path(tempfile.mkdtemp(prefix='openshsm-texture-late-link-', dir='/private/tmp'))
old_archive = Path(parent['archivePath'])
assert sha(old_archive) == parent['archiveSha256']
archive = cache / 'libnwiiruntime.a'
shutil.copyfile(old_archive, archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], check=True, capture_output=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
members = {}
for member in subprocess.check_output(['/usr/bin/ar', '-t', str(old_archive)], text=True).splitlines():
    if member.startswith('__'):
        continue
    before = subprocess.check_output(['/usr/bin/ar', '-p', str(old_archive), member])
    after = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    assert hashlib.sha256(after).hexdigest() == sha(obj) if member == 'texture_cache_gl.cpp.o' else before == after
    members[member] = hashlib.sha256(after).hexdigest()
link = list(parent['linkCommand'])
link[link.index(str(old_archive))] = str(archive)
exe = cache / 'OpenSHSMStockTextureLate'
link[link.index('-o') + 1] = str(exe)
linked = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert linked.returncode == 0, linked.stderr[-3000:]
retained = {}
for arg in link:
    if Path(arg).suffix in ('.o', '.a') and arg != str(archive):
        path = (Path(arg) if Path(arg).is_absolute() else root / 'export/build' / arg).resolve()
        retained[str(path)] = sha(path)
output = root / 'window-texture-late'
output.mkdir(exist_ok=True)
(output / 'build.json').write_text(json.dumps({
    'result': 'BOUNDED_LATE_TEXTURE_DIAGNOSTICS_LINKED_UNVERIFIED',
    'parentBuildSha256': sha(parent_path), 'parentComponentSha256': sha(component_path),
    'preparationSha256': sha(proof_path), 'sourcePath': str(source), 'sourceSha256': sha(source),
    'originalSourcePath': str(original), 'sourcePatch': proof['sourcePatch'],
    'textureObjectPath': str(obj), 'textureObjectSha256': sha(obj),
    'archivePath': str(archive), 'archiveSha256': sha(archive), 'members': members,
    'linkCommand': link, 'executablePath': str(exe), 'executableSha256': sha(exe),
    'retainedInputs': retained, 'arguments': proof['runtimeCompileCommand'][1:proof['runtimeCompileCommand'].index('-H')],
    'dependencies': {**proof['dependencies'], str(Path(__file__).resolve()): sha(Path(__file__)),
        str(proof_path): sha(proof_path), str(source): sha(source), str(header): sha(header)},
    'limits': ['Only texture observer object changed, all other archive/member/guest/master/VI/deadline/audio inputs exact.',
        'Before/after copies do not synchronize guest producer; enabled actual GL/native/live acceptance pending.']}, indent=2) + '\n')
print('BOUNDED_LATE_TEXTURE_DIAGNOSTICS_LINKED_UNVERIFIED', exe)

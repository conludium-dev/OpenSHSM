"""Optimize only the identical current texture-cache source, retaining binding/eviction fixes and current IOSO2 phases."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-texture-o2'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-ios-o2-phases/build.json'
parent = json.loads(parent_path.read_text())
for path, digest in {**parent['dependencies'], **parent['retainedInputs']}.items():
    assert sha(Path(path)) == digest
original = root / 'headless-texture-eviction/texture_cache_gl.cpp'
prior_path = original.parent / 'build.json'
prior = json.loads(prior_path.read_text())
assert sha(original) == prior['sourceSha256']
records = json.loads((root / 'headless-tev-banks/build.json').read_text())['compiled']
flags = next(row['arguments'] for row in records if row['member'] == 'texture_cache_gl.cpp.o')
assert not any(arg.startswith('-O') for arg in flags)
arguments = flags + ['-O2']
source, obj = output / 'texture_cache_gl.cpp', output / 'texture_cache_gl.cpp.o'
source.write_bytes(original.read_bytes())
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=90)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2500:]
command = list(parent['linkCommand'])
old_archive = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
assert hashlib.sha256(subprocess.check_output(['/usr/bin/ar', '-p', str(old_archive), 'texture_cache_gl.cpp.o'])).hexdigest() == prior['objectSha256']
cache = Path(tempfile.mkdtemp(prefix='openshsm-texture-o2-', dir='/private/tmp'))
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
    if member == 'texture_cache_gl.cpp.o':
        assert hashlib.sha256(after).hexdigest() == sha(obj)
    else:
        assert before == after
    members[member] = hashlib.sha256(after).hexdigest()
command[command.index(str(old_archive))] = str(archive)
exe = cache / 'OpenSHSMStockTextureO2'
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
    'result': 'IDENTICAL_TEXTURE_CACHE_O2_BUILT_EXECUTION_UNVERIFIED', 'parentBuildSha256': sha(parent_path),
    'priorCacheBuildSha256': sha(prior_path), 'originalSourcePath': str(original),
    'sourceSha256': sha(source), 'objectSha256': sha(obj), 'arguments': arguments, 'originalArguments': flags,
    'archivePath': str(archive), 'archiveSha256': sha(archive), 'members': members, 'linkCommand': command,
    'executablePath': str(exe), 'executableSha256': sha(exe), 'retainedInputs': inputs,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), original, source]},
    'limits': ['Current fixed cache source byte-identical/O2sole addedflag, no format/hash/eviction/EFB/GL binding changes.',
        'Only texture_cache_gl object replaced; IOSO2/main-VI observer/master/all75guests/renderer/audio/clock unchanged.',
        'Large executable Mac temporary cache, source/evidence/assets onData; no publication.',
        'Real GL pixels/bindings/cache invalidation/eviction and live performance/visual/audio pending.']}, indent=2) + '\n')
print('IDENTICAL_TEXTURE_CACHE_O2_BUILT_EXECUTION_UNVERIFIED', exe)

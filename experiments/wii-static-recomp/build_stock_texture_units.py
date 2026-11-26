"""Move slot selection before cache upload; preserve existing renderer/runtime/guest state."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'headless-texture-units'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
proof_path = root / 'texture-binding-research/verification.json'
assert json.loads(proof_path.read_text())['result'] == 'REAL_GL_TEXTURE_BINDING_MISS_CLOBBER_REPRODUCED'
base_path = root / 'headless-psq-scale/build.json'
base = json.loads(base_path.read_text())
for path, expected in {**base['dependencies'], **base['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
command = list(base['linkCommand'])
old = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
assert sha(old) == base['archiveSha256']
tev = json.loads((root / 'headless-tev-banks/build.json').read_text())
record = next(row for row in tev['compiled'] if row['member'] == 'renderer_gl.cpp.o')
original = root / 'headless-tev-banks/renderer_gl.cpp'
assert sha(original) == record['sourceSha256']
assert hashlib.sha256(subprocess.check_output(['/usr/bin/ar', '-p', str(old), 'renderer_gl.cpp.o'])).hexdigest() == record['objectSha256']
text = original.read_text()
before = '''              GLuint tex = nwii::runtime::hle::TextureCache::get().get_texture(
                  *g_ctx_ptr, stage);
              glActiveTexture(GL_TEXTURE0 + i);'''
after = '''              glActiveTexture(GL_TEXTURE0 + i);
              GLuint tex = nwii::runtime::hle::TextureCache::get().get_texture(
                  *g_ctx_ptr, stage);'''
assert text.count(before) == 1
text = text.replace(before, after)
assert text.replace(after, before) == original.read_text()
source, obj = output / 'renderer_gl.cpp', output / 'renderer_gl.cpp.o'
source.write_text(text)
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
archive = output / 'libnwiiruntime.a'
shutil.copy2(old, archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], capture_output=True, check=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], capture_output=True, check=True)
retained = {}
for member in subprocess.check_output(['/usr/bin/ar', '-t', str(old)], text=True).splitlines():
    if member.startswith('__') or member == 'renderer_gl.cpp.o':
        continue
    data = subprocess.check_output(['/usr/bin/ar', '-p', str(old), member])
    assert data == subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    retained[member] = hashlib.sha256(data).hexdigest()
command[command.index(str(old))] = str(archive)
exe = output / 'OpenSHSMStockTextureUnits'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
(output / 'build.json').write_text(json.dumps({'result': 'TEXTURE_UNIT_BIND_ORDER_BUILT_GAME_UNVERIFIED',
    'baseBuildSha256': sha(base_path), 'proofSha256': sha(proof_path), 'originalSourceSha256': sha(original),
    'sourceSha256': sha(source), 'objectSha256': sha(obj), 'archiveSha256': sha(archive),
    'executableSha256': sha(exe), 'linkCommand': command, 'retainedRuntimeMembers': retained,
    'dependencies': {str(Path(__file__).resolve()): sha(Path(__file__).resolve())},
    'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).suffix == '.o'},
    'limits': ['Only active texture-unit selection moved before cache call, no new state/ABI/texture arithmetic.',
        'One renderer object changed; all other runtime members/all75guest objects inclPSQ optimization retained.',
        'Cache eviction/presentation/FIFO/state lifetime and actual visual/game acceptance still pending.']}, indent=2) + '\n')
print('TEXTURE_UNIT_BIND_ORDER_BUILT_GAME_UNVERIFIED')

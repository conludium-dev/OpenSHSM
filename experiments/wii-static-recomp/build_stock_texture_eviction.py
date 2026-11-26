"""Evict unbound managed textures only; preserve GL bindings and existing cache/ABI."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'headless-texture-eviction'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
proof_path = root / 'texture-eviction-research/component-verification.json'
assert json.loads(proof_path.read_text())['result'] == 'BOUND_TEXTURE_EVICTION_LOSS_REPRODUCED'
base_path = root / 'headless-texture-units/build.json'
base = json.loads(base_path.read_text())
for path, expected in {**base['dependencies'], **base['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
command = list(base['linkCommand'])
old = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
assert sha(old) == base['archiveSha256']
parent = json.loads((root / 'headless-tev-banks/build.json').read_text())
record = next(row for row in parent['compiled'] if row['member'] == 'texture_cache_gl.cpp.o')
original = root / 'headless-tev-banks/texture_cache_gl.cpp'
assert sha(original) == record['sourceSha256']
assert hashlib.sha256(subprocess.check_output(['/usr/bin/ar', '-p', str(old), 'texture_cache_gl.cpp.o'])).hexdigest() == record['objectSha256']
text = original.read_text()
before = '    if (cache.size() > 512)\n        clear();'
assert text.count(before) == 1
after = '''    if (cache.size() > 512) {
        GLint active = 0, units = 0;
        glGetIntegerv(GL_ACTIVE_TEXTURE, &active);
        glGetIntegerv(GL_MAX_COMBINED_TEXTURE_IMAGE_UNITS, &units);
        std::vector<GLuint> bound;
        for (GLint unit = 0; unit < units; ++unit) {
            glActiveTexture(GL_TEXTURE0 + unit);
            GLint texture = 0;
            glGetIntegerv(GL_TEXTURE_BINDING_2D, &texture);
            bound.push_back(GLuint(texture));
        }
        glActiveTexture(active);
        for (auto item = cache.begin(); item != cache.end();) {
            if (std::find(bound.begin(), bound.end(), item->second) != bound.end()) {
                ++item;
            } else {
                glDeleteTextures(1, &item->second);
                item = cache.erase(item);
            }
        }
    }'''
text = '#include <algorithm>\n#include <vector>\n' + text.replace(before, after)
assert text.replace('#include <algorithm>\n#include <vector>\n', '', 1).replace(after, before) == original.read_text()
source, obj = output / 'texture_cache_gl.cpp', output / 'texture_cache_gl.cpp.o'
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
    if member.startswith('__') or member == 'texture_cache_gl.cpp.o':
        continue
    data = subprocess.check_output(['/usr/bin/ar', '-p', str(old), member])
    assert data == subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    retained[member] = hashlib.sha256(data).hexdigest()
command[command.index(str(old))] = str(archive)
exe = output / 'OpenSHSMStockTextureEviction'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
(output / 'build.json').write_text(json.dumps({'result': 'BOUND_TEXTURE_EVICTION_BUILT_GAME_UNVERIFIED',
    'baseBuildSha256': sha(base_path), 'proofSha256': sha(proof_path), 'sourceSha256': sha(source),
    'originalSourceSha256': sha(original), 'objectSha256': sha(obj), 'archiveSha256': sha(archive),
    'executableSha256': sha(exe), 'linkCommand': command, 'retainedRuntimeMembers': retained,
    'dependencies': {str(Path(__file__).resolve()): sha(Path(__file__).resolve())},
    'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).suffix == '.o'},
    'limits': ['Existing managed cache only; evict unbound objects above512, protect actual GL2D bindings/allunits, restore activeunit.',
        'No header/ABI/new registry/cache/renderer/guest changes; EFB pool remains independent and untouched.',
        'Real GPU stress/gameplay/flicker/FPS acceptance still pending.']}, indent=2) + '\n')
print('BOUND_TEXTURE_EVICTION_BUILT_GAME_UNVERIFIED')

"""Reproduce real linked texture-cache GL side effects, not original game visual acceptance."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'texture-binding-research'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'headless-tev-banks/build.json'
parent = json.loads(parent_path.read_text())
base_path = root / 'headless-psq-scale/build.json'
base = json.loads(base_path.read_text())
for path, expected in {**base['dependencies'], **base['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
command = list(base['linkCommand'])
archive = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
assert sha(archive) == base['archiveSha256']
renderer = root / 'headless-tev-banks/renderer_gl.cpp'
text = renderer.read_text()
marker = '''              GLuint tex = nwii::runtime::hle::TextureCache::get().get_texture(
                  *g_ctx_ptr, stage);
              glActiveTexture(GL_TEXTURE0 + i);
              glBindTexture(GL_TEXTURE_2D, tex);'''
assert text.count(marker) == 1
record = next(row for row in parent['compiled'] if row['member'] == 'renderer_gl.cpp.o')
source, obj = public / 'stock_texture_binding_probe.cpp', output / 'probe.cpp.o'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2000:]
command[command.index(str(root / 'headless-tev-banks/main.cpp.o'))] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
command.insert(1, str(obj))
exe = output / 'binding-probe'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
(output / 'probe.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
assert 'TEXTURE_BINDING_MISS_CLOBBER_REPRODUCED' in result.stdout
(output / 'verification.json').write_text(json.dumps({'result': 'REAL_GL_TEXTURE_BINDING_MISS_CLOBBER_REPRODUCED',
    'baseBuildSha256': sha(base_path), 'rendererSourceSha256': sha(renderer), 'archiveSha256': sha(archive),
    'probeSourceSha256': sha(source), 'executableSha256': sha(exe), 'logSha256': sha(output / 'probe.log'),
    'verifierSha256': sha(Path(__file__).resolve()),
    'limits': ['Actual linked TextureCache on hidden native GL driver; cold/all-hit/one-miss/activate-before-load control.',
        'Synthetic three I8 planes, renderer binding order mirrored; not actual SHSM draw/FIFO/color/flicker acceptance.']}, indent=2) + '\n')
print(result.stdout.strip())

"""Pin cache-only change, native GPU stress and bounded game captures."""
from pathlib import Path
import ast
import hashlib
import json
import subprocess
from PIL import Image

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'headless-texture-eviction'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, expected in {**build['dependencies'], **build['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
exe, archive = output / 'OpenSHSMStockTextureEviction', output / 'libnwiiruntime.a'
assert sha(exe) == build['executableSha256'] and sha(archive) == build['archiveSha256']
for member, expected in build['retainedRuntimeMembers'].items():
    assert hashlib.sha256(subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])).hexdigest() == expected
original = root / 'headless-tev-banks/texture_cache_gl.cpp'
assert sha(original) == build['originalSourceSha256']
tree = ast.parse((public / 'build_stock_texture_eviction.py').read_text())
values = {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
    and node.targets[0].id in ('before', 'after')}
source = output / 'texture_cache_gl.cpp'
assert sha(source) == build['sourceSha256']
assert source.read_text() == '#include <algorithm>\n#include <vector>\n' + original.read_text().replace(values['before'], values['after'])
component_path = output / 'component-verification.json'
component = json.loads(component_path.read_text())
assert component['result'] == 'BOUND_TEXTURE_EVICTION_PROTECTION_PASS1600'
assert component['buildSha256'] == sha(build_path)
run_path = root / 'headless-sc-pc-headless-windowed-texture-eviction-live-result.json'
run = json.loads(run_path.read_text())
assert run['windowed'] and run['capture'] and run['executableSha256'] == sha(exe)
log = root / 'headless-sc-pc-headless-windowed-texture-eviction-live.log'
assert sha(log) == run['logSha256']
text = log.read_text(errors='replace')
assert 'GX shader compilation failed' not in text and 'GX shader link failed' not in text
captures = {}
for bmp in sorted(root.glob('headless-sc-pc-texture-eviction-live-efb_*.bmp')):
    png = bmp.with_suffix('.png')
    image = Image.open(bmp).convert('RGBA')
    image.save(png)
    assert Image.open(png).convert('RGBA').tobytes() == image.tobytes()
    captures[bmp.stem] = {'bmpSha256': sha(bmp), 'pngSha256': sha(png)}
assert captures
(output / 'live-audit.json').write_text(json.dumps({'result': 'BOUND_TEXTURE_EVICTION_SOURCE_GPU_LIVE_PINNED',
    'buildSha256': sha(build_path), 'componentSha256': sha(component_path), 'runSha256': sha(run_path),
    'logSha256': sha(log), 'captures': captures, 'auditorSha256': sha(Path(__file__).resolve()),
    'limits': ['Only managed cache eviction block changed; exact source/archive/other members/allguests and1600GPU admissions checked.',
        'Real bounded GUI smoke/captures; no live eviction counter, temporal flicker/FPS/profile/gameplay or Wii oracle acceptance.']}, indent=2) + '\n')
print('BOUND_TEXTURE_EVICTION_SOURCE_GPU_LIVE_PINNED', len(captures))

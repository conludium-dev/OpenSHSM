"""Pin actual corrected renderer source/archive/live screenshots without claiming temporal acceptance."""
from pathlib import Path
import hashlib
import json
from PIL import Image

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'headless-texture-units'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, expected in {**build['dependencies'], **build['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
assert sha(output / 'OpenSHSMStockTextureUnits') == build['executableSha256']
assert sha(output / 'libnwiiruntime.a') == build['archiveSha256']
source = output / 'renderer_gl.cpp'
assert sha(source) == build['sourceSha256']
after = '''              glActiveTexture(GL_TEXTURE0 + i);
              GLuint tex = nwii::runtime::hle::TextureCache::get().get_texture(
                  *g_ctx_ptr, stage);'''
before = '''              GLuint tex = nwii::runtime::hle::TextureCache::get().get_texture(
                  *g_ctx_ptr, stage);
              glActiveTexture(GL_TEXTURE0 + i);'''
assert source.read_text().count(after) == 1
assert source.read_text().replace(after, before) == (root / 'headless-tev-banks/renderer_gl.cpp').read_text()
proof_path = root / 'texture-binding-research/verification.json'
proof = json.loads(proof_path.read_text())
assert proof['result'] == 'REAL_GL_TEXTURE_BINDING_MISS_CLOBBER_REPRODUCED'
assert sha(proof_path) == build['proofSha256']
run_path = root / 'headless-sc-pc-headless-windowed-texture-units-live-result.json'
run = json.loads(run_path.read_text())
assert run['result'] == 'BOUNDED_STOCK_RUN_COMPLETE' and run['windowed'] and run['capture']
assert run['executableSha256'] == build['executableSha256']
log = root / 'headless-sc-pc-headless-windowed-texture-units-live.log'
assert sha(log) == run['logSha256']
text = log.read_text(errors='replace')
assert 'GX shader compilation failed' not in text and 'GX shader link failed' not in text
captures = {}
for bmp in sorted(root.glob('headless-sc-pc-texture-units-live-efb_*.bmp')):
    png = bmp.with_suffix('.png')
    pixels = Image.open(bmp).convert('RGBA')
    pixels.save(png)
    assert Image.open(png).convert('RGBA').tobytes() == pixels.tobytes()
    captures[bmp.stem] = {'bmpSha256': sha(bmp), 'pngSha256': sha(png), 'size': list(pixels.size)}
assert captures
(output / 'live-audit.json').write_text(json.dumps({'result': 'TEXTURE_UNIT_SOURCE_GPU_PROOF_LIVE_CAPTURES_PINNED',
    'buildSha256': sha(build_path), 'proofSha256': sha(proof_path), 'runSha256': sha(run_path),
    'logSha256': sha(log), 'captures': captures, 'auditorSha256': sha(Path(__file__).resolve()),
    'limits': ['Corrected single ordering change, actual linked cache hidden GL proof, bounded real renderer run.',
        'Screenshots converted losslessly, human inspection recorded separately; temporal flicker/FPS/gameplay not certified.',
        'Cache eviction and remaining GX/presentation paths still unverified; no original Wii hardware oracle.']}, indent=2) + '\n')
print('TEXTURE_UNIT_SOURCE_GPU_PROOF_LIVE_CAPTURES_PINNED', len(captures))

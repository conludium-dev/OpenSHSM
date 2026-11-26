"""Pin corrected-bank build/component/GPU/live evidence without visual acceptance claims."""
from pathlib import Path
import hashlib
import json
from PIL import Image

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'headless-tev-banks'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
assert sha(output / 'OpenSHSMStockTEVBanks') == build['executableSha256']
assert sha(output / 'libnwiiruntime.a') == build['archiveSha256']
assert sha(output / 'include/runtime/gx_state.h') == build['gxHeaderSha256']
for row in build['compiled']:
    assert sha(output / row['member']) == row['objectSha256']
for path, expected in build['dependencies'].items():
    assert sha(Path(path)) == expected
run_path = root / 'headless-sc-pc-headless-gx-windowed-tev-banks-live-result.json'
run = json.loads(run_path.read_text())
assert run['terminalReturncode'] == 0 and run['deadlineReached']
assert run['executableSha256'] == build['executableSha256']
assert run['experimentalExecutable'] == 'headless-tev-banks/OpenSHSMStockTEVBanks'
headers_path = output / 'guest-header-verification.json'
headers = json.loads(headers_path.read_text())
assert headers['buildSha256'] == sha(build_path) and headers['units'] == 75
pixel_path = output / 'pixel-verification.json'
pixels = json.loads(pixel_path.read_text())
assert pixels['result'] == 'TEV_BANK_NATIVE_GPU_PIXEL_PASS4'
assert pixels['pixelBuildSha256'] == sha(output / 'pixel-build.json')
log = root / 'headless-sc-pc-headless-gx-windowed-tev-banks-live.log'
assert sha(log) == run['logSha256']
text = log.read_text(errors='replace')
assert 'GX shader compilation failed' not in text and 'GX shader link failed' not in text
captures = {}
for frame in (1200, 3900, 6000):
    bmp = root / f'headless-sc-pc-tev-banks-live-efb_{frame}.bmp'
    png = bmp.with_suffix('.png')
    assert Image.open(bmp).convert('RGBA').tobytes() == Image.open(png).convert('RGBA').tobytes()
    captures[str(frame)] = {'bmpSha256': sha(bmp), 'pngSha256': sha(png)}
(output / 'live-audit.json').write_text(json.dumps({'result': 'TEV_BANK_BUILD_GPU_LIVE_EVIDENCE_PINNED_VISUAL_PARTIAL',
    'buildSha256': sha(build_path), 'runSha256': sha(run_path), 'guestHeaderReportSha256': sha(headers_path),
    'pixelReportSha256': sha(pixel_path), 'captures': captures, 'auditorSha256': sha(Path(__file__).resolve()),
    'cacheIRQRecords': text.count('[Cache IRQ]'),
    'limits': ['Terminal bounded120s run and byte-equal capture conversions, not gameplay/visual/performance acceptance.',
        'Human visual inspection and user feedback documented separately; purple flashes and low video performance remain.',
        'GPU fixture proves four synthetic pixels, not full renderer/Wii equivalence; cache IRQ records do not establish exact SC boundary return.']}, indent=2) + '\n')
print('TEV_BANK_BUILD_GPU_LIVE_EVIDENCE_PINNED_VISUAL_PARTIAL')

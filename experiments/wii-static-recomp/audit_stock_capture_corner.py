"""Compare paired owned EFB/back-buffer captures without changing their original pixels."""
from pathlib import Path
import hashlib
import json
import subprocess
from PIL import Image

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
run_path = Path('/private/tmp/openshsm-run-mgngcxnz/headless-sc-pc-headless-windowed-dispatch-select-result.json')
run = json.loads(run_path.read_text())
assert run['terminalReturncode'] == 0 and run['capture'] and run['temporaryCapture']
prefix = Path(run['capturePrefix'])
assert prefix.parent.parent == Path('/private/tmp') and prefix.parent.name.startswith('openshsm-captures-')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
audit_path = root / 'window-dispatch-select/live-input-audit.json'
audit = json.loads(audit_path.read_text())
assert sha(run_path) == audit['runSha256']
build_path = root / 'window-dispatch-select/build.json'
build = json.loads(build_path.read_text())
assert sha(build_path) == audit['buildSha256'] and build['executableSha256'] == run['executableSha256']
archive = Path(build['archivePath'])
assert sha(archive) == build['archiveSha256']
gx_source, gx_object = root / 'headless-tev-banks/gx.cpp', root / 'headless-tev-banks/gx.cpp.o'
gx_member = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), 'gx.cpp.o'])
assert hashlib.sha256(gx_member).hexdigest() == sha(gx_object)
texture_path = root / 'window-texture-o2/build.json'
texture = json.loads(texture_path.read_text())
texture_source = root / 'headless-texture-eviction/texture_cache_gl.cpp'
assert sha(texture_source) == texture['sourceSha256']
texture_member = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), 'texture_cache_gl.cpp.o'])
assert hashlib.sha256(texture_member).hexdigest() == texture['objectSha256']
timer_path = root / 'window-vi-timer/build.json'
timer = json.loads(timer_path.read_text())
main_source, main_object = timer_path.parent / 'main.cpp', timer_path.parent / 'main.cpp.o'
assert sha(main_source) == timer['sourceSha256'] and sha(main_object) == timer['objectSha256']
assert str(main_object) in build['linkCommand']
records = []
for tick in (1800, 6600, 6900):
    efb_path = Path(str(prefix) + f'_{tick}.bmp')
    debug_path = Path(str(prefix) + f'_debug_{tick}.bmp')
    display_path = debug_path.with_suffix('.display.png')
    record = next(row for row in audit['captures'] if row['bmpPath'] == str(debug_path))
    assert sha(debug_path) == record['bmpSha256'] and sha(display_path) == record['pngSha256']
    with Image.open(efb_path) as source, Image.open(debug_path) as rendered, Image.open(display_path) as display:
        efb = source.convert('RGB')
        debug = rendered.convert('RGB')
        assert display.convert('RGB').tobytes() == debug.tobytes()
        assert efb.size == (640, 480) and debug.size == (960, 540)
        rgb_path = efb_path.with_suffix('.display.png')
        efb.save(rgb_path)
        with Image.open(rgb_path) as checked:
            assert checked.convert('RGB').tobytes() == efb.tobytes()
        # Blit maps source pixel centers to 960x540; selected interior samples avoid edge filtering.
        points = []
        for x, y in ((480, 474), (500, 474), (580, 474), (630, 474), (400, 474), (500, 460)):
            dx = int((x + 0.5) * debug.width / efb.width)
            dy = int((y + 0.5) * debug.height / efb.height)
            points.append({'efbXY': [x, y], 'debugXY': [dx, dy],
                'efbRGB': list(efb.getpixel((x, y))), 'debugRGB': list(debug.getpixel((dx, dy)))})
        records.append({'tick': tick, 'efbPath': str(efb_path), 'efbSha256': sha(efb_path),
            'efbDisplayPath': str(rgb_path), 'efbDisplaySha256': sha(rgb_path),
            'debugSha256': sha(debug_path), 'displayRgbExact': True, 'points': points})
report = {
    'result': 'PAIRED_EFB_BACKBUFFER_EXACT_RGB_CAPTURE_CORNER_AUDITED',
    'runSha256': sha(run_path), 'packetAuditSha256': sha(audit_path),
    'auditorSha256': sha(Path(__file__)), 'records': records,
    'implementationEvidence': {
        'mainSourceSha256': sha(main_source), 'mainObjectSha256': sha(main_object),
        'gxSourceSha256': sha(gx_source), 'linkedGxObjectSha256': sha(gx_object),
        'textureSourceSha256': sha(texture_source), 'linkedTextureObjectSha256': texture['objectSha256'],
        'findings': [
            'Main calls ProcessGXFifo before blit/EFB readback/debug overlay/backbuffer capture, in one rendering loop.',
            'Current GX carry selects completed BP0x52 bit0x4000 boundary before Render, retaining unfinished command tail.',
            'FIFO mutex protects queue transfer, not texture reads during Render; current texture decoding reads shared guest memory.',
            'Concurrent texture-buffer reuse is a hypothesis, not dynamically proved; no captured texture source bytes at tick6900.']},
    'limits': ['Original BMP files unchanged; RGB display conversions preserve channels, no gamma/alpha correction.',
        'Matching corner features in EFB and back buffer rule out display-PNG conversion as sole cause.',
        'Sparse paired captures do not independently prove visibility on screen or origin in original decoder/texture upload/FIFO.',
        'Mapped center samples are qualitative correspondence, not exact GL_LINEAR interpolation oracle.']}
path = run_path.parent / 'capture-corner-audit.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
print(json.dumps(records[-1]['points'], indent=2))

"""Verify measured presentation delay and guarded software pacing; inspect captured pixels honestly."""
from pathlib import Path
import hashlib
import json
import re
from PIL import Image

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
before = root / 'window-present'
after = root / 'window-paced'
text = (before / 'main.cpp').read_text()
changes = [
    ('      SDL_GL_SetSwapInterval(1);', '      SDL_GL_SetSwapInterval(0);'),
    ('      if (headless) std::this_thread::sleep_for(std::chrono::milliseconds(16));',
        '      std::this_thread::sleep_for(std::chrono::milliseconds(16));'),
]
for old, new in changes:
    assert text.count(old) == 1
    text = text.replace(old, new)
assert text == (after / 'main.cpp').read_text()
records = {}
for variant, directory, exe_name in (
    ('window-present', before, 'OpenSHSMStockWindowPresent'),
    ('window-paced', after, 'OpenSHSMStockWindowPaced'),
):
    manifest = json.loads((directory / 'build.json').read_text())
    assert sha(directory / 'main.cpp') == manifest['sourceSha256']
    assert sha(directory / exe_name) == manifest['executableSha256']
    assert sha(root / 'ipc-cpbp/libnwiiruntime.a') == manifest['archiveSha256']
    for name, digest in manifest['retainedObjects'].items():
        assert sha(root / 'export/build' / name) == digest
    label = variant + '-headless-gx-windowed'
    run = json.loads((root / (label + '-result.json')).read_text())
    log = root / (label + '.log')
    assert run['windowed'] and run['deadlineReached']
    assert run['terminalReturncode'] in (0, -9, -15)
    assert run['executableSha256'] == manifest['executableSha256']
    assert run['logSha256'] == sha(log)
    text = log.read_text()
    begin = int(re.search(r'\[WindowStartup\] us=(\d+) phase=swap begin', text)[1])
    end = int(re.search(r'\[WindowStartup\] us=(\d+) phase=swap end', text)[1])
    delay = end - begin
    if variant == 'window-present':
        assert delay > 1000000 and '[ GPU Hang detected ]' in text
    else:
        assert delay < 100000 and '[ GPU Hang detected ]' not in text
        assert 'efb_nonblack=306560/307200' in text
        assert 'linked=1 glErr=0x0' in text
    records[variant] = {'firstSwapMicroseconds': delay, 'logSha256': sha(log),
        'retainedObjects': len(manifest['retainedObjects'])}
bmp = root / 'window-paced-efb_300.bmp'
png = root / 'window-paced-efb_300.png'
with Image.open(bmp) as a, Image.open(png) as b:
    assert a.size == b.size == (640, 480)
    assert a.convert('RGBA').tobytes() == b.convert('RGBA').tobytes()
    colours = a.convert('RGBA').getcolors(640 * 480)
    assert colours is not None
(after / 'startup-audit.json').write_text(json.dumps({
    'result': 'WINDOW_PRESENTATION_DELAY_AB_PASS', 'observations': records,
    'captureBmpSha256': sha(bmp), 'capturePngSha256': sha(png), 'captureColours': colours,
    'limits': ['Host software presentation adapter: VSync0 and16ms loop pacing, not exact Wii frame timing.',
        'Visually inspected EFB is nearly uniform dark grey, no recognizable logo/menu/first-screen acceptance.',
        'Original resources, watchdog, timebase/EventScheduler and full runtime archive unchanged between A/B.']
}, indent=2) + '\n')
print('PASS actual presentation A/B:', records['window-present']['firstSwapMicroseconds'],
    '→', records['window-paced']['firstSwapMicroseconds'], 'microseconds')
print('Captured pixels verified; near-uniform dark-grey frame, NOT first-screen proof')

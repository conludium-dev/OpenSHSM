"""Compare owned paired title EFB/back buffers and unchanged diagnostic-parent captures."""
from pathlib import Path
import hashlib
import json
from PIL import Image

sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
runs = [
    ('parent', Path('/private/tmp/openshsm-run-nbabr6mn'), 'texture-late', 'window-texture-late'),
    ('candidate', Path('/private/tmp/openshsm-run-8wo8q7_3'), 'pe-execute', 'window-pe-execute')]
records = []
for label, artifacts, tag, build_directory in runs:
    run_path = artifacts / f'headless-sc-pc-headless-windowed-{tag}-result.json'
    run = json.loads(run_path.read_text())
    build_path = root / build_directory / 'build.json'
    build = json.loads(build_path.read_text())
    assert run['terminalReturncode'] == 0 and run['executableSha256'] == build['executableSha256']
    assert sha(artifacts / f'headless-sc-pc-headless-windowed-{tag}.log') == run['logSha256']
    prefix = Path(run['capturePrefix'])
    assert prefix.parent.parent == Path('/private/tmp') and prefix.parent.name.startswith('openshsm-captures-')
    for tick in (1500, 1800, 2100):
        paths = {'efb': Path(str(prefix) + f'_{tick}.bmp'), 'backbuffer': Path(str(prefix) + f'_debug_{tick}.bmp')}
        images = {}
        entries = {}
        for kind, path in paths.items():
            with Image.open(path) as image:
                rgb = image.convert('RGB')
                png = path.with_suffix('.display.png')
                rgb.save(png)
                with Image.open(png) as checked:
                    assert checked.convert('RGB').tobytes() == rgb.tobytes()
                images[kind] = rgb
                entries[kind] = {'path': str(path), 'sha256': sha(path), 'displayPath': str(png),
                    'displaySha256': sha(png), 'size': list(rgb.size)}
        samples = []
        for x, y in ((64, 448), (320, 448), (480, 448), (600, 448), (620, 464), (320, 384)):
            dx = int((x + 0.5) * images['backbuffer'].width / images['efb'].width)
            dy = int((y + 0.5) * images['backbuffer'].height / images['efb'].height)
            samples.append({'efbXY': [x, y], 'backbufferXY': [dx, dy],
                'efbRGB': list(images['efb'].getpixel((x, y))),
                'backbufferRGB': list(images['backbuffer'].getpixel((dx, dy)))})
        records.append({'variant': label, 'tick': tick, 'runSha256': sha(run_path),
            'buildSha256': sha(build_path), 'images': entries, 'samples': samples})
path = runs[1][1] / 'title-paired-audit.json'
path.write_text(json.dumps({'result': 'OWNED_TITLE_EFB_BACKBUFFER_PARENT_CANDIDATE_PAIRS_AUDITED',
    'auditorSha256': sha(Path(__file__)), 'records': records,
    'limits': ['Original BMP unchanged, RGB display copies preserve channels exactly/no gamma or alpha compositing.',
        'Equal capture tick is presentation-loop index, not same original animation/frame/context.',
        'Mapped center samples approximate GL_LINEAR correspondence, not independent exact scaler oracle.',
        'Different EFB/backbuffer corner pixels can localize presentation hazard but do not alone prove GL state or texture ownership cause.']}, indent=2) + '\n')
print('OWNED_TITLE_EFB_BACKBUFFER_PARENT_CANDIDATE_PAIRS_AUDITED', path)
print(json.dumps(next(row['samples'] for row in records if row['variant'] == 'candidate' and row['tick'] == 1800), indent=2))

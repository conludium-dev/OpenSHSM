"""Private chronological contact sheets of completed EFB captures, not guessed movie frames."""
from pathlib import Path
import argparse
import hashlib
import json
import re
from PIL import Image, ImageDraw

parser = argparse.ArgumentParser()
parser.add_argument('--artifacts', type=Path, required=True)
args = parser.parse_args()
root = args.artifacts.resolve()
assert root.parent == Path('/private/tmp') and root.name.startswith('openshsm-pc-play-')
record_path = root / 'result.json'
record = json.loads(record_path.read_text())
assert record['startupCapture'] and not record['deadlineEnabled']
files = sorted((path for path in root.glob('startup_*.bmp') if re.fullmatch(r'startup_\d+\.bmp', path.name)),
    key=lambda path: int(path.stem.split('_')[-1]))
rows = []
for path in files:
    number = int(path.stem.split('_')[-1])
    assert 1 <= number <= 1200
    assert number <= 15 or number % 15 == 0
    with Image.open(path) as picture:
        picture.load()
        assert picture.size == (640, 480)
    rows.append({'frame': number, 'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
assert rows
selected = [row for row in rows if row['frame'] in (1, 5, 10, 15) or row['frame'] > 15]
pages = []
for page in range((len(selected) + 19) // 20):
    batch = selected[page * 20:(page + 1) * 20]
    sheet = Image.new('RGB', (1280, 1040), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    for index, row in enumerate(batch):
        x, y = (index % 4) * 320, (index // 4) * 208
        with Image.open(row['path']) as picture:
            sheet.paste(picture.convert('RGB').resize((256, 192)), (x, y + 16))
        draw.text((x + 4, y + 2), 'present ' + str(row['frame']), fill=(255, 255, 255))
    output = root / f'startup-contact-{page}.png'
    sheet.save(output)
    pages.append({'path': str(output), 'sha256': hashlib.sha256(output.read_bytes()).hexdigest()})
report = {'result': 'COMPLETED_EFB_STARTUP_CAPTURES_INDEXED', 'captures': rows, 'contactSheets': pages,
    'scriptSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'limits': ['Presentation order, not an exact wallclock or Wii hardware trace.',
        'EFB pixels before debug overlay, window scaling and swap; not desktop screenshots.',
        'First15 presentations plus every15 through1200; later unsampled frames may differ.',
        'Capture readback affects performance; not an FPS benchmark.']}
output = root / f'startup-capture-index-{rows[-1]["frame"]}.json'
assert not output.exists()
output.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], len(rows), rows[-1]['frame'], [page['path'] for page in pages])

"""Compare captured original decoder output with independent full-range THP decode."""
from pathlib import Path
import argparse
import hashlib
import json
import re

parser = argparse.ArgumentParser()
parser.add_argument('--tag', required=True)
parser.add_argument('--variant', choices=('window-lc-thp', 'window-quantization', 'window-idct-observe', 'window-thp-dcbz', 'window-fp-context', 'window-psq-anomaly', 'window-fp-guard', 'interpreter-carry-corrected', 'interpreter-addze-corrected', 'headless-sc-pc'), default='window-lc-thp')
args = parser.parse_args()
assert re.fullmatch(r'[a-z0-9-]{1,40}', args.tag)
root = Path('work/private-game/static-recomp').resolve()
game = Path('work/private-game/disc/DATA/files/MOVIES/PUBDEV')
sha = lambda data: hashlib.sha256(data).hexdigest()
source = game.read_bytes()
assert source[:4] == b'THP\0'
word = lambda offset: int.from_bytes(source[offset:offset + 4], 'big')
assert (word(0x44), word(0x48)) == (640, 480)
reference = (root / 'thp-reference/pubdev-first3.yuvj420p').read_bytes()
assert len(reference) == 3 * 460800
prefix = root / 'stock-baseline' / (args.variant + '-' + args.tag + '-thp')
offset, size = word(0x28), word(0x18)
records = []
packets = []
for frame in range(word(0x14)):
    assert offset + size <= len(source)
    video_size = word(offset + 8)
    assert video_size <= size - 16
    packets.append(source[offset + 16:offset + 16 + video_size])
    next_size = word(offset)
    offset += size
    size = next_size
capture_matches = []
for index in range(3):
    path = Path(str(prefix) + f'-packet{index}.bin')
    if path.exists():
        captured = path.read_bytes()
        capture_matches.append({'captureIndex': index, 'sha256': sha(captured),
            'matchingOriginalFrames': [frame for frame, packet in enumerate(packets) if packet == captured]})

def untile(data, width, height):
    result = bytearray(len(data))
    for y in range(height):
        for x in range(0, width, 8):
            start = ((y // 4) * (width // 8) + x // 8) * 32 + (y % 4) * 8
            result[y * width + x:y * width + x + 8] = data[start:start + 8]
    return bytes(result)

def metrics(actual, expected, width):
    errors = [abs(a - b) for a, b in zip(actual, expected)]
    assert len(actual) == len(expected)
    return {'meanAbsoluteError': sum(errors) / len(errors), 'maxAbsoluteError': max(errors),
        'fractionWithin2': sum(error <= 2 for error in errors) / len(errors),
        'outliersAbove2': sum(error > 2 for error in errors),
        'outlierSamples': [{'x': index % width, 'y': index // width,
            'actual': actual[index], 'reference': expected[index]} for index in
            [index for index, error in enumerate(errors) if error > 2][:16]],
        'actualRange': [min(actual), max(actual)], 'referenceRange': [min(expected), max(expected)]}

for frame in range(3):
    original_packet = packets[frame]
    row = {'frame': frame, 'originalPacketSha256': sha(original_packet), 'planes': {}}
    row['matchingCaptureIndices'] = [item['captureIndex'] for item in capture_matches
        if frame in item['matchingOriginalFrames']]
    position = frame * 460800
    for name, width, height in [('Y', 640, 480), ('U', 320, 240), ('V', 320, 240)]:
        length = width * height
        expected = reference[position:position + length]
        position += length
        path = Path(str(prefix) + f'-frame{frame}-{name}.bin')
        if not path.exists():
            row['planes'][name] = {'missing': True}
            continue
        actual = path.read_bytes()
        assert len(actual) == length
        row['planes'][name] = {'sha256': sha(actual), 'linear': metrics(actual, expected, width),
            'gxI8Tiles8x4': metrics(untile(actual, width, height), expected, width)}
    records.append(row)
report = {'result': 'THP_INDEPENDENT_DECODE_COMPARISON', 'gameSha256': sha(source),
    'comparisonRecipeSha256': sha(Path(__file__).read_bytes()),
    'referenceSha256': sha(reference), 'capturePacketMatches': capture_matches, 'frames': records,
    'limits': ['FFmpeg full-range yuvj420p reference, not physical Wii oracle.',
        'Small IDCT rounding differences may be legal; neither layout is presumed correct.',
        'Missing captures do not establish decoder correctness or failure.']}
(root / 'stock-baseline' / (args.variant + '-' + args.tag + '-comparison.json')).write_text(
    json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))

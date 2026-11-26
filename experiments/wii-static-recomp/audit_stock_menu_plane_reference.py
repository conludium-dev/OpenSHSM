"""Compare private captured I8 planes with independent decoding of the owned LOOP."""
from pathlib import Path
import argparse
import hashlib
import json
import mmap
import struct
import subprocess
import tempfile
from PIL import Image, ImageChops

parser = argparse.ArgumentParser()
parser.add_argument('--artifacts', type=Path, required=True)
args = parser.parse_args()
artifacts = args.artifacts.resolve()
assert artifacts.parent == Path('/private/tmp') and artifacts.name.startswith('openshsm-run-')
project = Path(__file__).resolve().parents[2]
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
audit_path = artifacts / 'menu-texture-audit.json'
packet_path = artifacts / 'profile-input-audit.json'
audit = json.loads(audit_path.read_text())
packet_audit = json.loads(packet_path.read_text())
assert audit['result'] == 'OWNED_MENU_TEXTURE_WINDOW_AUDITED'
assert all(sha(path) == value for path, value in audit['dependencies'].items())
proof_path = project / 'work/private-game/static-recomp/stock-baseline/headless-thp-snapshot/colored-replay/verification.json'
proof = json.loads(proof_path.read_text())
ffmpeg = Path(proof['referenceCommand'][0])
assert sha(ffmpeg) == proof['ffmpegSha256']
movie = project / 'work/private-game/disc/DATA/files/MOVIES/LOOP'
data = movie.read_bytes()
assert data[:4] == b'THP\0'
assert struct.unpack_from('>f', data, 16)[0] == 30
assert int.from_bytes(data[20:24], 'big') == 359
assert tuple(int.from_bytes(data[p:p + 4], 'big') for p in (68, 72)) == (640, 480)
assert any(source['path'] == str(movie) and source['sha256'] == sha(movie)
    for source in packet_audit['movieSources'])
cache = Path(tempfile.mkdtemp(prefix='openshsm-menu-plane-reference-', dir='/private/tmp'))
raw_path = cache / 'original-loop-yuvj420p.bin'
command = [str(ffmpeg), '-nostdin', '-hide_banner', '-loglevel', 'error', '-i', str(movie),
    '-an', '-frames:v', '359', '-pix_fmt', 'yuvj420p', '-f', 'rawvideo', str(raw_path)]
decoded = subprocess.run(command, capture_output=True, timeout=60)
assert decoded.returncode == 0, decoded.stderr.decode(errors='replace')
frame_size = 640 * 480 * 3 // 2
assert raw_path.stat().st_size == 359 * frame_size

def untile(raw, width, height):
    assert width % 8 == 0 and height % 4 == 0 and len(raw) == width * height
    linear = bytearray(len(raw))
    for y in range(height):
        for x in range(0, width, 8):
            offset = ((y // 4) * (width // 8) + x // 8) * 32 + (y % 4) * 8
            linear[y * width + x:y * width + x + 8] = raw[offset:offset + 8]
    return Image.frombytes('L', (width, height), bytes(linear))

def error(actual, reference):
    histogram = ImageChops.difference(actual, reference).histogram()
    count = actual.width * actual.height
    return {'meanAbsoluteError': sum(index * value for index, value in enumerate(histogram)) / count,
        'differentPixels': count - histogram[0],
        'maximumAbsoluteError': max(index for index, value in enumerate(histogram) if value)}

rows = []
with raw_path.open('rb') as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as original:
    for texture in audit['records']:
        assert texture['format'] == 1
        width, height = texture['width'], texture['height']
        planes = [('Y', 'r4', 0)] if (width, height) == (640, 480) else [
            ('U', 'r5', 307200), ('V', 'r6', 384000)]
        matches = []
        for packet in packet_audit['records']:
            for plane, field, offset in planes:
                if (texture['address'] & 0x1FFFFFFF) == (packet['begin'][field] & 0x1FFFFFFF):
                    for match in packet['moduloPositionMatches']:
                        if match['movie'] == 'LOOP':
                            matches.append((plane, field, offset, packet, match['frame']))
        actual_planes = sorted({(plane, field, offset) for plane, field, offset, _, _ in matches})
        assert len(actual_planes) <= 1
        if not actual_planes:
            continue
        plane, _, offset = actual_planes[0]
        for name, path_key, hash_key in [('before', 'beforePath', 'beforeSha256'),
            ('after', 'rawPath', 'rawSha256')]:
            source = Path(texture[path_key])
            assert source.parent.parent == artifacts and sha(source) == texture[hash_key]
            picture = untile(source.read_bytes(), width, height)
            scores = []
            for frame in range(359):
                position = frame * frame_size + offset
                reference = Image.frombytes('L', (width, height), original[position:position + width * height])
                scores.append({'frame': frame, **error(picture, reference)})
            ranked = sorted(scores, key=lambda row: (row['meanAbsoluteError'], row['frame']))
            overlapped = [frame for _, _, _, packet, frame in matches
                if packet['end'] and texture['beforeUs'] <= packet['end']['hostUs']
                and texture['afterUs'] >= packet['begin']['hostUs']]
            completed = [(packet['end']['hostUs'], frame) for _, _, _, packet, frame in matches
                if packet['end'] and packet['end']['hostUs'] <= texture['beforeUs']]
            last_completed = max(completed)[1] if completed else None
            selected = sorted(set(overlapped + ([last_completed] if last_completed is not None else [])))
            preview = cache / f'texture-{texture["sequence"]}-{plane}-{name}.png'
            picture.save(preview)
            best = ranked[0]['frame']
            position = best * frame_size + offset
            reference_path = cache / f'original-{best}-{plane}.png'
            Image.frombytes('L', (width, height), original[position:position + width * height]).save(reference_path)
            rows.append({'sequence': texture['sequence'], 'plane': plane, 'sample': name,
                'changedBytes': texture['changedBytes'], 'bestMatches': ranked[:6],
                'overlappingDecoderOriginalFrames': sorted(set(overlapped)),
                'lastCompletedSameAddressOriginalFrame': last_completed,
                'selectedFrameErrors': [scores[frame] for frame in selected],
                'previewPath': str(preview), 'previewSha256': sha(preview),
                'referencePath': str(reference_path), 'referenceSha256': sha(reference_path)})
assert rows
report = {'result': 'OWNED_LOOP_ALL359_PLANES_VS_CAPTURED_I8_AUDITED',
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), audit_path,
        packet_path, proof_path, ffmpeg, movie]},
    'referenceCommand': command, 'rawPath': str(raw_path), 'rawSha256': sha(raw_path),
    'rows': rows, 'limits': [
        'Independent full-range FFmpeg planes, not physical Wii output or bit-exact PPC decoder oracle.',
        'Lowest plane error is a heuristic; repeated/similar planes do not uniquely identify original frame.',
        'Captured unsynchronized source copies can tear; after-copy need not be completed decoder output.',
        'Address and time associations do not prove write instruction, cross-plane frame ownership or band causation.',
        'No runtime synchronization fix, performance claim, asset change or release promotion.']}
path = cache / 'verification.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
print(json.dumps([{key: row[key] for key in ['sequence', 'plane', 'sample', 'bestMatches',
    'overlappingDecoderOriginalFrames', 'lastCompletedSameAddressOriginalFrame', 'selectedFrameErrors']}
    for row in rows if row['changedBytes']], indent=2))

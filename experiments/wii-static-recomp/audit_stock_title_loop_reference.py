"""Search the user's original LOOP THP for the observed title color band."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess
import tempfile
from PIL import Image

project = Path(__file__).resolve().parents[2]
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
proof_path = project / 'work/private-game/static-recomp/stock-baseline/headless-thp-snapshot/colored-replay/verification.json'
proof = json.loads(proof_path.read_text())
ffmpeg = Path(proof['referenceCommand'][0])
assert sha(ffmpeg) == proof['ffmpegSha256']
movie = project / 'work/private-game/disc/DATA/files/MOVIES/LOOP'
data = movie.read_bytes()
assert data[:4] == b'THP\0'
frames = int.from_bytes(data[20:24], 'big')
fps = struct.unpack_from('>f', data, 16)[0]
assert frames == 359 and fps == 30 and tuple(int.from_bytes(data[p:p + 4], 'big') for p in (68, 72)) == (640, 480)
artifacts = Path('/private/tmp/openshsm-run-u7rvp7w_')
run_path = artifacts / 'headless-sc-pc-headless-windowed-context-stage-live-result.json'
run = json.loads(run_path.read_text())
assert run['terminalReturncode'] == 0 and run['deadlineReached']
prefix = Path(run['capturePrefix'])
capture = Path(str(prefix) + '_1500.bmp')
assert capture.is_file()
with Image.open(capture) as picture:
    assert picture.size == (640, 480)
    observed = picture.convert('RGB').resize((80, 60), Image.Resampling.BOX).tobytes()
observed_red = 0
observed_count = 0
for y in range(30, 56):
    for x in range(4, 76):
        offset = (y * 80 + x) * 3
        r, g, b = observed[offset:offset + 3]
        observed_red += r > g + 25 and r > b + 25
        observed_count += 1
cache = Path(tempfile.mkdtemp(prefix='openshsm-loop-reference-', dir='/private/tmp'))
command = [str(ffmpeg), '-nostdin', '-hide_banner', '-loglevel', 'error', '-i', str(movie),
    '-vf', 'scale=80:60:flags=area', '-an', '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1']
decoded = subprocess.run(command, capture_output=True, timeout=60)
assert decoded.returncode == 0, decoded.stderr.decode(errors='replace')
amount = 80 * 60 * 3
assert len(decoded.stdout) == frames * amount
raw_path = cache / 'original-loop-rgb80x60.bin'
raw_path.write_bytes(decoded.stdout)
rows = []
for frame in range(frames):
    pixels = decoded.stdout[frame * amount:(frame + 1) * amount]
    errors = []
    red = 0
    count = 0
    for y in range(30, 56):
        for x in range(4, 76):
            offset = (y * 80 + x) * 3
            rgb = pixels[offset:offset + 3]
            expected = observed[offset:offset + 3]
            errors.extend(abs(a - b) for a, b in zip(rgb, expected))
            red += rgb[0] > rgb[1] + 25 and rgb[0] > rgb[2] + 25
            count += 1
    rows.append({'frame': frame, 'bottomMeanAbsoluteRgbError': sum(errors) / len(errors),
        'bottomRedFraction': red / count})
best = min(rows, key=lambda row: row['bottomMeanAbsoluteRgbError'])
red_best = max(rows, key=lambda row: row['bottomRedFraction'])
selected = sorted({0, best['frame'], red_best['frame']})
previews = []
for frame in selected:
    preview = cache / f'original-loop-{frame}.png'
    cmd = [str(ffmpeg), '-nostdin', '-hide_banner', '-loglevel', 'error', '-i', str(movie),
        '-vf', f'select=eq(n\\,{frame})', '-frames:v', '1', '-an', str(preview)]
    run = subprocess.run(cmd, capture_output=True, timeout=30)
    assert run.returncode == 0, run.stderr.decode(errors='replace')
    previews.append({'frame': frame, 'path': str(preview), 'sha256': sha(preview), 'command': cmd})
report = {'result': 'OWNED_LOOP_ALL359_INDEPENDENT_RGB_REFERENCE_SEARCHED',
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), movie, ffmpeg, proof_path, run_path, capture]},
    'referenceCommand': command, 'rawPath': str(raw_path), 'rawSha256': sha(raw_path),
    'bestBottomMatch': best, 'mostRedBottom': red_best, 'rows': rows, 'previews': previews,
    'observedBottomRedFraction': observed_red / observed_count,
    'limits': ['Independent FFmpeg decode of exact user-owned LOOP, not physical Wii/GX oracle.',
        'All359 source frames searched; box/area thumbnail comparison is a heuristic, not original frame identity.',
        'Native EFB may contain separate UI/TEV effects; absence in movie alone cannot rule out intentional game-rendered effects.',
        'No runtime fix, source asset change, original behavior equivalence or visual promotion.']}
path = cache / 'verification.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
print(json.dumps({'best': best, 'red': red_best, 'observedRedFraction': observed_red / observed_count,
    'previews': previews}, indent=2))

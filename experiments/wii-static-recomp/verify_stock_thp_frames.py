"""Validate same-packet whole-frame native output, with a separately reproduced FFmpeg reference."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp').resolve()
baseline = root / 'stock-baseline'
public = Path('experiments/wii-static-recomp').resolve()
output = baseline / 'headless-constant-fp/frame-comparison'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
game = Path('work/private-game/disc/DATA/files/MOVIES/PUBDEV').resolve()
assert sha(game) == '389954a82304dead3b96bda3e5d71361114f7b2407cca9e5de42e4e63361a80a'
ffmpeg = Path('work/research/video-tools/macos-arm64/package/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1').resolve()
command = [str(ffmpeg), '-nostdin', '-hide_banner', '-loglevel', 'error', '-i', str(game),
    '-map', '0:v:0', '-frames:v', '3', '-an', '-pix_fmt', 'yuvj420p', '-f', 'rawvideo', 'pipe:1']
decoded = subprocess.run(command, capture_output=True, check=True, timeout=60)
reference = root / 'thp-reference/pubdev-first3.yuvj420p'
assert decoded.stdout == reference.read_bytes() and len(decoded.stdout) == 3 * 460800
reference_sha = sha(reference)
reports, inputs = {}, {}
for name, build_name, tag in [('baseline', 'headless-movie-timing', 'frame-baseline'),
                               ('candidate', 'headless-constant-fp', 'frame-constant')]:
    build_path = baseline / build_name / 'build.json'
    build = json.loads(build_path.read_text())
    for path, expected in {**build['dependencies'], **build['retainedLinkInputs']}.items():
        assert sha(Path(path)) == expected
    exe = Path(build['linkCommand'][build['linkCommand'].index('-o') + 1])
    assert sha(exe) == build['executableSha256']
    archive = next(Path(arg) for arg in build['linkCommand'] if Path(arg).name == 'libnwiiruntime.a')
    assert sha(archive) == build['archiveSha256']
    run_path = baseline / f'headless-sc-pc-headless-{tag}-result.json'
    run = json.loads(run_path.read_text())
    assert run['result'] == 'BOUNDED_STOCK_RUN_COMPLETE' and run['thpDump'] and not run['windowed']
    assert run['executableSha256'] == build['executableSha256']
    assert run['traceOnly'] == '80209d80,80217d30'
    log = baseline / f'headless-sc-pc-headless-{tag}.log'
    assert sha(log) == run['logSha256']
    subprocess.run(['python3', str(public / 'compare_stock_thp.py'), '--variant', 'headless-sc-pc', '--tag', tag],
        capture_output=True, check=True, timeout=60)
    report_path = baseline / f'headless-sc-pc-{tag}-comparison.json'
    report = json.loads(report_path.read_text())
    assert report['gameSha256'] == sha(game) and report['referenceSha256'] == reference_sha
    assert report['comparisonRecipeSha256'] == sha(public / 'compare_stock_thp.py')
    reports[name] = report
    inputs[name] = {'buildSha256': sha(build_path), 'runSha256': sha(run_path), 'logSha256': sha(log),
        'comparisonSha256': sha(report_path), 'prefix': str(baseline / f'headless-sc-pc-{tag}-thp')}
rows = []
for frame in (0, 1):
    a, b = reports['baseline']['frames'][frame], reports['candidate']['frames'][frame]
    assert a['matchingCaptureIndices'] and b['matchingCaptureIndices']
    assert a['originalPacketSha256'] == b['originalPacketSha256']
    planes = {}
    for plane, length in [('Y', 307200), ('U', 76800), ('V', 76800)]:
        paths = [Path(inputs[name]['prefix'] + f'-frame{frame}-{plane}.bin') for name in ('baseline', 'candidate')]
        values = [path.read_bytes() for path in paths]
        assert len(values[0]) == len(values[1]) == length
        assert sha(paths[0]) == a['planes'][plane]['sha256'] and sha(paths[1]) == b['planes'][plane]['sha256']
        planes[plane] = {'equalBytes': values[0] == values[1], 'bytes': length,
            'baselineSha256': sha(paths[0]), 'candidateSha256': sha(paths[1]),
            'referenceMetricsBaseline': a['planes'][plane]['gxI8Tiles8x4'],
            'referenceMetricsCandidate': b['planes'][plane]['gxI8Tiles8x4']}
    rows.append({'frame': frame, 'originalPacketSha256': a['originalPacketSha256'], 'planes': planes})
equal = all(value['equalBytes'] for row in rows for value in row['planes'].values())
report = {'result': 'TWO_COMPLETE_NATIVE_FRAMES_BYTE_IDENTICAL' if equal else 'COMPLETE_NATIVE_FRAME_DIFFERENCE_FOUND',
    'comparedBytes': 921600, 'inputs': inputs, 'frames': rows,
    'gameSha256': sha(game), 'ffmpegSha256': sha(ffmpeg), 'referenceCommand': command,
    'referenceSha256': reference_sha, 'verifierSha256': sha(Path(__file__).resolve()),
    'limits': ['Two complete first PUBDEV frames, same compressed packets; independent native runs with IRQ/callbacks.',
        'Not controlled timing replay, complete movie equivalence or original Wii hardware pixel oracle.',
        'FFmpeg reference reproduced byte-for-byte; small IDCT differences remain, not silently accepted as exact Wii behavior.',
        'Third captured packet can correspond to a later frame because of skipping; missing frame2 remains unverified.',
        'No GPU/draw/presentation/flicker/color or whole-game acceptance.']}
(output / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], report['comparedBytes'])
print(json.dumps([{'frame': row['frame'], 'planes': {name: {'equal': value['equalBytes'],
    'meanError': value['referenceMetricsCandidate']['meanAbsoluteError'],
    'maxError': value['referenceMetricsCandidate']['maxAbsoluteError']} for name, value in row['planes'].items()}} for row in rows], indent=2))

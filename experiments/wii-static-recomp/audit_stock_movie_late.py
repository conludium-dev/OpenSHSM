"""Match delayed live packets against owned THP files without confusing GX batches with new video frames."""
from pathlib import Path
import hashlib
import json
import re

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-movie-late'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert (output / 'stock_movie_input.h').read_bytes() == Path('experiments/wii-static-recomp/stock_movie_input.h').read_bytes()
base = Path('experiments/wii-static-recomp/audit_stock_movie_input.py')
script = base.read_text()
patches = [
    ("output = root / 'window-movie-input'", "output = root / 'window-movie-late'"),
    ("'ACTUAL_CONTEXT_PACKET_CAPTURE_FRAME_STATE_IDENTICAL3'", "'MOVIE_LATE_GATE_PACKET_FRAME_STATE_IDENTICAL3'"),
    ("cap['buildSha256'] == sha(build_path)", "cap['buildSha256'] == sha(root / 'window-movie-input/build.json')"),
    ("sha(output / 'OpenSHSMStockMovieInput')", "sha(Path(build['executablePath']))"),
    ('headless-sc-pc-headless-windowed-movie-input', 'headless-sc-pc-headless-windowed-movie-late-retry'),
    ('headless-sc-pc-movie-input-movie-timing.jsonl', 'headless-sc-pc-movie-late-retry-movie-timing.jsonl')]
for before, after in patches:
    assert before in script
    script = script.replace(before, after)
scope = {'__file__': __file__}
exec(compile(script, str(base), 'exec'), scope)
run = scope['run']
assert run['movieCaptureAfterMs'] == 70000
text = (root / 'headless-sc-pc-headless-windowed-movie-late-retry.log').read_text()
host = re.findall(r'^\[HostPhases\] hostUs=(\d+) elapsedUs=(\d+)', text, re.M)
assert host
first_epoch_end, first_epoch_duration = map(int, host[0])
first_timing_us = scope['timing'][0]['hostUs']
assert first_timing_us >= first_epoch_end - first_epoch_duration + 69000000
report_path = output / 'live-input-audit.json'
report = json.loads(report_path.read_text())
report.update(result='DELAYED_LIVE_OWNED_MOVIE_PACKETS_AUDITED',
    baseAuditorSha256=sha(base), gateDelayMs=run['movieCaptureAfterMs'],
    firstTimingHostUs=first_timing_us, firstHostPhaseEndUs=first_epoch_end)
report['limits'].extend(['Delayed observer opens after70s from first movie boundary; first timestamp checked against host phase epoch.',
    'A boundary may open inside a frame, so initial unmatched return is retained, not treated as completed decode.',
    'Only late bounded observation, not controlled whole-game/unique displayed video FPS, visual/audio/profile acceptance.'])
report_path.write_text(json.dumps(report, indent=2) + '\n')
print('DELAYED_LIVE_OWNED_MOVIE_PACKETS_AUDITED')

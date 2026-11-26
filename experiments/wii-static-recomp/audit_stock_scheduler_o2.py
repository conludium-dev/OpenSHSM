"""Audit current scheduler-only live packets and exact shared-frame comparisons, retaining context caveats."""
from pathlib import Path
import hashlib
import json
import re
import statistics
from PIL import Image

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-scheduler-o2'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
parent_path = root / 'window-movie-late/build.json'
assert sha(parent_path) == build['parentBuildSha256']
base = Path('experiments/wii-static-recomp/audit_stock_movie_input.py')
script = base.read_text()
unit_block = '''for unit, change in build['changes'].items():
    assert (output / f'output_{unit}.cpp').read_bytes() == Path(change['originalPath']).read_bytes()
    assert sha(output / f'output_{unit}.cpp.o') == change['objectSha256']
'''
patches = [
    ("output = root / 'window-movie-input'", "output = root / 'window-scheduler-o2'"),
    (unit_block, ''),
    ("'ACTUAL_CONTEXT_PACKET_CAPTURE_FRAME_STATE_IDENTICAL3'", "'SCHEDULER_O2_CONTRACT_CALLBACK4_SDK7_SC3_LATE18_EQUAL'"),
    ("cap['buildSha256'] == sha(build_path)", "cap['buildSha256'] == sha(root / 'window-movie-input/build.json')"),
    ("sha(output / 'OpenSHSMStockMovieInput')", "sha(Path(build['executablePath']))"),
    ('headless-sc-pc-headless-windowed-movie-input', 'headless-sc-pc-headless-windowed-scheduler-o2'),
    ('headless-sc-pc-movie-input-movie-timing.jsonl', 'headless-sc-pc-scheduler-o2-movie-timing.jsonl')]
for before, after in patches:
    assert before in script
    script = script.replace(before, after)
scope = {'__file__': __file__}
exec(compile(script, str(base), 'exec'), scope)
run = scope['run']
delay_ms = run['movieCaptureAfterMs']
assert isinstance(delay_ms, int) and 0 <= delay_ms <= 180000
assert run['capture'] and run['temporaryCapture']
text = (root / 'headless-sc-pc-headless-windowed-scheduler-o2.log').read_text()
host = re.findall(r'^\[HostPhases\] hostUs=(\d+) elapsedUs=(\d+)', text, re.M)
assert host
first_epoch_end, first_epoch_duration = map(int, host[0])
assert scope['timing'][0]['hostUs'] >= first_epoch_end - first_epoch_duration + max(0, delay_ms - 1000) * 1000
prior_path = root / 'window-movie-late/live-input-audit.json'
prior = json.loads(prior_path.read_text())
assert prior['result'] == 'DELAYED_LIVE_OWNED_MOVIE_PACKETS_AUDITED'
def key(record):
    if len(record['moduloPositionMatches']) != 1 or not record['end']:
        return None
    match = record['moduloPositionMatches'][0]
    return match['movie'], match['frame'], record['capture']['packetSha256']
old = {key(record): record for record in prior['records'] if key(record)}
matched = [{'movie': key(record)[0], 'frame': key(record)[1],
    'packetSha256': key(record)[2], 'beforeWallUs': old[key(record)]['wallUs'], 'afterWallUs': record['wallUs']}
    for record in scope['records'] if key(record) in old]
matched_summary = []
for movie in sorted({record['movie'] for record in matched}):
    group = [record for record in matched if record['movie'] == movie]
    matched_summary.append({'movie': movie, 'pairs': len(group),
        'beforeMedianUs': statistics.median(record['beforeWallUs'] for record in group),
        'afterMedianUs': statistics.median(record['afterWallUs'] for record in group)})
audio_base = Path('experiments/wii-static-recomp/audit_stock_bounds_visual.py')
audio = audio_base.read_text()
start = audio.index("fields = ['wallUs'")
end = audio.index('timing = root /', start)
audio_scope = {'text': text}
exec('import re\n' + audio[start:end], audio_scope)
prefix = Path(run['capturePrefix'])
assert prefix.parent.parent == Path('/private/tmp') and prefix.parent.name.startswith('openshsm-captures-')
assert prefix.name == 'headless-sc-pc-scheduler-o2-efb'
captures = []
for bmp in sorted(prefix.parent.glob(prefix.name + '_debug_*.bmp')):
    png = bmp.with_suffix('.display.png')
    with Image.open(bmp) as image:
        rgb = image.convert('RGB')
        rgb.save(png)
        with Image.open(png) as check:
            assert check.convert('RGB').tobytes() == rgb.tobytes()
    captures.append({'bmpPath': str(bmp), 'bmpSha256': sha(bmp), 'pngPath': str(png), 'pngSha256': sha(png)})
assert captures
report_path = output / 'live-input-audit.json'
report = json.loads(report_path.read_text())
report.update(result='SCHEDULER_O2_LATE_LIVE_PACKET_VISUAL_AUDIO_AUDITED',
    baseAuditorSha256=sha(base), priorAuditSha256=sha(prior_path), matchedFrames=matched,
    matchedSummary=matched_summary, captures=captures, lastCallback=audio_scope['callback'][-1],
    lastAdma=audio_scope['adma'][-1], excludedCallbackRows=text.count('[AudioCallback] ') - len(audio_scope['callback']),
    excludedAdmaRows=text.count('[ADMAAccounting] ') - len(audio_scope['adma']))
report['limits'].extend(['Matched exact same movie/frame/packet bytes across separate sessions, not identical guest/IRQ/device histories or controlled FPS percent.',
    'Original RGBA and exact RGB display copies retained; visual inspection recorded separately.',
    'ADMA and callback epochs differ: own balances only, no cross subtraction or speaker quality proof.',
    'No profile/save/story/controller/physical Wii/full movie acceptance or promotion.'])
report_path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'])
print(json.dumps({'matched': matched_summary, 'lastCallback': report['lastCallback'],
    'lastAdma': report['lastAdma'], 'capturePrefix': str(prefix)}, indent=2))

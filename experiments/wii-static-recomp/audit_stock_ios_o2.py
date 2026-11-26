"""Audit exact live packets plus real captures/audio for the identical-source O2 candidate."""
from pathlib import Path
import hashlib
import json
import re
from PIL import Image

base = Path('experiments/wii-static-recomp/audit_stock_movie_input.py')
script = base.read_text()
unit_block = '''for unit, change in build['changes'].items():
    assert (output / f'output_{unit}.cpp').read_bytes() == Path(change['originalPath']).read_bytes()
    assert sha(output / f'output_{unit}.cpp.o') == change['objectSha256']
'''
patches = [("output = root / 'window-movie-input'", "output = root / 'window-ios-o2'"),
    (unit_block, ''),
    ("component['result'] == 'ACTUAL_CONTEXT_PACKET_CAPTURE_FRAME_STATE_IDENTICAL3'", "component['result'] == 'IOS_O2_CALLBACK4_FRAME3_SDK7_SC3_PASS'"),
    ("cap['buildSha256'] == sha(build_path)", "cap['buildSha256'] == build['parentBuildSha256']"),
    ("sha(output / 'OpenSHSMStockMovieInput')", "sha(Path(build['executablePath']))"),
    ('headless-sc-pc-headless-windowed-movie-input-result.json', 'headless-sc-pc-headless-windowed-ios-o2-result.json'),
    ('headless-sc-pc-headless-windowed-movie-input.log', 'headless-sc-pc-headless-windowed-ios-o2.log'),
    ('headless-sc-pc-movie-input-movie-timing.jsonl', 'headless-sc-pc-ios-o2-movie-timing.jsonl')]
for before, after in patches:
    assert script.count(before) == 1
    script = script.replace(before, after, 1)
scope = {'__file__': __file__}
exec(compile(script, str(base), 'exec'), scope)
root, output, build, run = scope['root'], scope['output'], scope['build'], scope['run']
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert (output / 'ios.cpp').read_bytes() == Path(build['originalSourcePath']).read_bytes()
assert sha(output / 'ios.cpp.o') == build['objectSha256']
assert build['arguments'] == build['originalArguments'] + ['-O2']
assert all('callbackProfile' not in row for row in scope['timing'])
assert run['capture']
log = root / 'headless-sc-pc-headless-windowed-ios-o2.log'
text = log.read_text()
fields = ['wallUs', 'calls', 'requested', 'supplied', 'missing', 'short', 'errors', 'final']
callback = [dict(zip(fields, map(int, row))) for row in re.findall(
    r'^\[AudioCallback\] ' + ' '.join(key + r'=(\d+)' for key in fields) + r'$', text, re.M)]
assert callback and callback[-1]['final'] == 1 and callback[-1]['errors'] == 0
for row in callback:
    assert row['requested'] == row['supplied'] + row['missing']
adma_fields = ['wallUs', 'input32', 'input48', 'accepted', 'dropped', 'flushAccepted', 'flushDropped',
    'supplied', 'requested', 'short', 'ring', 'tbFirst', 'tbLast', 'tbFrequency', 'tbWallUs']
adma = [dict(zip(adma_fields, map(int, row))) for row in re.findall(
    r'^\[ADMAAccounting\] ' + ' '.join(key + r'=(\d+)' for key in adma_fields) + r'$', text, re.M)]
assert adma
for row in adma:
    assert row['accepted'] - row['supplied'] == row['ring']
    if not row['input48']:
        assert row['input32'] == row['accepted'] + row['dropped']
captures = {}
for bmp in sorted(root.glob('headless-sc-pc-ios-o2-efb_debug_*.bmp')):
    png = bmp.with_suffix('.display.png')
    with Image.open(bmp) as image:
        rgb = image.convert('RGB')
        rgb.save(png)
        with Image.open(png) as check:
            assert check.convert('RGB').tobytes() == rgb.tobytes()
    captures[bmp.stem] = {'bmpSha256': sha(bmp), 'pngSha256': sha(png)}
assert captures
packet_report_path = output / 'live-input-audit.json'
packet_report = json.loads(packet_report_path.read_text())
(output / 'live-audit.json').write_text(json.dumps({
    'result': 'IDENTICAL_IOS_O2_LIVE_PACKET_CAPTURE_AUDIO_AUDITED',
    'buildSha256': sha(output / 'build.json'), 'packetAuditSha256': sha(packet_report_path),
    'baseAuditorSha256': sha(base), 'auditorSha256': sha(Path(__file__)),
    'packetSummary': packet_report['summary'], 'captures': captures,
    'lastCallback': callback[-1], 'lastAdma': adma[-1],
    'excludedCallbackRows': text.count('[AudioCallback] ') - len(callback),
    'excludedAdmaRows': text.count('[ADMAAccounting] ') - len(adma),
    'limits': ['Identical-source O2 only for IOS; guest/master/audio/clock preserved and native callback/frame/SDK/SC tests passed.',
        'Exact owned packet identity in one live startup session, not controlled identical live contexts or full-game speedup.',
        'Captures RGB checked, visual inspection documented separately; not proof flicker-free/audio speaker quality.',
        'Callback and ADMA snapshots from different epochs; only each own balance compared.',
        'Profile/save/story/controller/physical Wii acceptance and candidate promotion remain pending.']}, indent=2) + '\n')
print('IDENTICAL_IOS_O2_LIVE_PACKET_CAPTURE_AUDIO_AUDITED', len(captures))
print(json.dumps({'lastCallback': callback[-1], 'lastAdma': adma[-1]}, indent=2))

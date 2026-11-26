"""Audit real candidate captures/audio accounting without treating repeated buffer addresses as frame identity."""
from pathlib import Path
import hashlib
import json
import re
import statistics
from PIL import Image

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-bounds-lookup'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
for filename, key in [('fixed.cpp', 'masterSourceSha256'), ('fixed.cpp.o', 'masterObjectSha256'),
    ('bounds.cpp', 'lookupSourceSha256'), ('bounds.cpp.o', 'lookupObjectSha256'),
    ('OpenSHSMStockBoundsLookup', 'executableSha256')]:
    assert sha(output / filename) == build[key]
component_path = output / 'component-verification.json'
component = json.loads(component_path.read_text())
assert component['result'] == 'BOUNDS_LOOKUP_FRAME_STATE_IDENTICAL3'
assert component['buildSha256'] == sha(build_path)
run_path = root / 'headless-sc-pc-headless-windowed-bounds-visual-result.json'
run = json.loads(run_path.read_text())
assert run['executableSha256'] == build['executableSha256']
assert run['terminalReturncode'] == 0 and run['deadlineReached'] and not run['logLimitReached']
assert all(run[key] for key in ('windowed', 'capture', 'debugOverlay', 'dspSupply', 'wallTimebase', 'skipWiiNotices', 'movieTiming'))
log = root / 'headless-sc-pc-headless-windowed-bounds-visual.log'
assert sha(log) == run['logSha256']
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
assert '[ GPU Hang detected ]' not in text
timing = root / 'headless-sc-pc-bounds-visual-movie-timing.jsonl'
rows = [json.loads(line) for line in timing.read_text().splitlines()]
assert rows and len(rows) <= 4096 and all(row['serial'] == index for index, row in enumerate(rows))
pending, decode, unpaired, displaced = {}, [], [], []
for row in rows:
    if row['site'] not in (0x80209D80, 0x8020A044):
        continue
    key = (row['thread'], row['sp'])
    if row['site'] == 0x80209D80:
        if key in pending:
            displaced.append(pending[key])
        pending[key] = row
    else:
        begin = pending.pop(key, None)
        if begin is None:
            unpaired.append(row)
            continue
        if begin['lr'] != row['lr']:
            unpaired.extend([begin, row])
            continue
        decode.append({'begin': begin, 'end': row, 'wallUs': row['hostUs'] - begin['hostUs']})
assert decode and all(row['wallUs'] >= 0 for row in decode)
captures = {}
for bmp in sorted(root.glob('headless-sc-pc-bounds-visual-efb_debug_*.bmp')):
    png = bmp.with_suffix('.display.png')
    with Image.open(bmp) as image:
        rgb = image.convert('RGB')
        rgb.save(png)
        with Image.open(png) as check:
            assert check.convert('RGB').tobytes() == rgb.tobytes()
    captures[bmp.stem] = {'bmpSha256': sha(bmp), 'pngSha256': sha(png)}
assert captures
summary = {'decoderPairs': len(decode), 'medianWallUs': statistics.median(row['wallUs'] for row in decode),
    'returnValues': sorted(set(row['end']['r3'] for row in decode)),
    'distinctInputBufferAddresses': len({row['begin']['r3'] for row in decode}),
    'lastCallback': callback[-1], 'lastAdma': adma[-1], 'captures': len(captures)}
(output / 'visual-audit.json').write_text(json.dumps({
    'result': 'BOUNDS_LOOKUP_CAPTURES_AUDIO_ACCOUNTING_AUDITED', 'buildSha256': sha(build_path),
    'componentSha256': sha(component_path), 'runSha256': sha(run_path), 'timingSha256': sha(timing),
    'auditorSha256': sha(Path(__file__)), 'summary': summary, 'captures': captures,
    'callbackRows': callback, 'admaRows': adma, 'decoderPairs': decode,
    'excludedCallbackRows': text.count('[AudioCallback] ') - len(callback),
    'excludedAdmaRows': text.count('[ADMAAccounting] ') - len(adma),
    'unpaired': unpaired, 'displaced': displaced, 'pending': list(pending.values()),
    'limits': ['Captures generated and RGB pixels checked; visual inspection documented separately.',
        'Debug overlay GX FPS is surviving command-batch frequency, not unique video frames.',
        'Decoder input buffer addresses can be recycled; no packet bytes/frame IDs in prior observer, no exact-frame benchmark.',
        'ADMA and callback report epochs differ: never subtract their final totals.',
        'No speaker/listening/profile/save/controller/full-game/physical Wii acceptance.']}, indent=2) + '\n')
print('BOUNDS_LOOKUP_CAPTURES_AUDIO_ACCOUNTING_AUDITED')
print(json.dumps(summary, indent=2))

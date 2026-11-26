"""Audit existing-device callback integration and real terminal run; shortages remain explicit."""
from pathlib import Path
import hashlib
import json
import re
from PIL import Image

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-audio-callback'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
original = Path(build['originalPath'])
assert sha(original) == build['originalSha256']
expected = original.read_text()
for before, after in build['patches']:
    assert expected.count(before) == 1
    expected = expected.replace(before, after)
assert expected == (output / 'main.cpp').read_text()
assert sha(output / 'main.cpp') == build['sourceSha256']
assert sha(output / 'main.cpp.o') == build['objectSha256']
overlay = (public / 'stock_debug_overlay.h').read_text()
for before, after in build['overlayPatches']:
    assert overlay.count(before) == 1
    overlay = overlay.replace(before, after)
assert overlay == (output / 'stock_debug_overlay.h').read_text()
parent_path = root / 'window-pc-boot/build.json'
assert sha(parent_path) == build['parentBuildSha256']
command = json.loads(parent_path.read_text())['linkCommand']
main = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
command[command.index(main)] = str(output / 'main.cpp.o')
exe = output / 'OpenSHSMStockAudioCallback'
command[command.index('-o') + 1] = str(exe)
assert command == build['linkCommand']
assert sha(exe) == build['executableSha256']
component_path = output / 'component-verification.json'
component = json.loads(component_path.read_text())
assert component['buildSha256'] == sha(build_path)
assert component['result'] == 'AUDIO_CALLBACK_DSP_PCM_BOUNDS_SDL_LIFETIME_PASS'
run_path = root / 'headless-sc-pc-headless-windowed-audio-callback-live-result.json'
run = json.loads(run_path.read_text())
assert run['terminalReturncode'] == 0 and run['deadlineReached'] and not run['logLimitReached']
assert run['windowed'] and run['capture'] and run['dspSupply'] and run['wallTimebase'] and run['skipWiiNotices']
assert run['executableSha256'] == sha(exe)
log = root / 'headless-sc-pc-headless-windowed-audio-callback-live.log'
assert sha(log) == run['logSha256']
text = log.read_text()
fields = ['wallUs', 'calls', 'requested', 'supplied', 'missing', 'short', 'errors', 'final']
callback = [dict(zip(fields, map(int, match))) for match in re.findall(
    r'^\[AudioCallback\] ' + ' '.join(key + r'=(\d+)' for key in fields) + r'$', text, re.M)]
assert callback and callback[-1]['final'] == 1
last = callback[-1]
assert last['errors'] == 0 and last['requested'] == last['supplied'] + last['missing']
adma_fields = ['wallUs', 'input32', 'input48', 'accepted', 'dropped', 'flushAccepted', 'flushDropped',
    'supplied', 'requested', 'short', 'ring', 'tbFirst', 'tbLast', 'tbFrequency', 'tbWallUs']
adma = [dict(zip(adma_fields, map(int, match))) for match in re.findall(
    r'^\[ADMAAccounting\] ' + ' '.join(key + r'=(\d+)' for key in adma_fields) + r'$', text, re.M)]
assert adma
for row in adma:
    assert row['accepted'] - row['supplied'] == row['ring']
    if not row['input48']:
        assert row['input32'] == row['accepted'] + row['dropped']
assert text.count('[PCBoot] skipped console notice index=0 next=4') == 1
assert text.count('[PCBoot] skipped console notice index=5 next=6') == 1
assert '[ GPU Hang detected ]' not in text
captures = {}
for bmp in root.glob('headless-sc-pc-audio-callback-live-efb_debug_*.bmp'):
    png = bmp.with_suffix('.display.png')
    with Image.open(bmp) as image:
        rgb = image.convert('RGB')
        rgb.save(png)
        with Image.open(png) as check:
            assert check.convert('RGB').tobytes() == rgb.tobytes()
    captures[bmp.stem] = {'bmpSha256': sha(bmp), 'pngSha256': sha(png)}
assert captures
report = {'result': 'AUDIO_CALLBACK_SOURCE_COMPONENT_LIVE_AUDITED',
    'buildSha256': sha(build_path), 'componentSha256': sha(component_path), 'runSha256': sha(run_path),
    'auditorSha256': sha(Path(__file__)), 'callbackRows': callback, 'lastCallback': last,
    'admaRows': adma, 'lastAdma': adma[-1], 'maxRingFrames': max(row['ring'] for row in adma),
    'excludedRows': {'callback': text.count('[AudioCallback] ') - len(callback),
        'adma': text.count('[ADMAAccounting] ') - len(adma)}, 'captures': captures,
    'limits': ['Final callback row is after SDL close and coherent; live atomic snapshots may span increments.',
        'Different ADMA/callback report epochs, no cross-subtraction of last totals.',
        'Existing DSP observer may log under mutex in callback; not a hard realtime guarantee.',
        'No physical Wii/whole-game speed/controller/profile/story/full-FPS acceptance; release frozen.']}
(output / 'live-audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], len(captures))
print(json.dumps({key: report[key] for key in ['lastCallback', 'lastAdma', 'maxRingFrames', 'excludedRows']}, indent=2))

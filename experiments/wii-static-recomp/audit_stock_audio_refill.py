"""Audit actual consumer wiring and sampled conservation, without cross-epoch counter assumptions."""
from pathlib import Path
import hashlib
import json
import re
from PIL import Image

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-audio-refill'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, digest in {**build['dependencies'], **build['retainedLinkInputs']}.items():
    assert sha(Path(path)) == digest
parent_path = root / 'window-adma-deadline/build.json'
parent = json.loads(parent_path.read_text())
assert sha(parent_path) == build['parentBuildSha256']
archive = root / 'window-adma-deadline/libnwiiruntime.a'
assert sha(archive) == build['archiveSha256'] == parent['archiveSha256']
before, after = build['mainPatch']
source = output / 'main.cpp'
assert sha(source) == build['sourceSha256']
assert source.read_text().removeprefix('#include "stock_audio_refill.h"\n').replace(after, before, 1) == (
    root / 'window-debug-overlay/main.cpp').read_text()
overlay = (output / 'stock_debug_overlay.h').read_text()
for before, after in reversed(build['overlayPatch']):
    assert overlay.count(after) == 1
    overlay = overlay.replace(after, before)
assert overlay == Path('experiments/wii-static-recomp/stock_debug_overlay.h').read_text()
command = list(parent['linkCommand'])
old_main = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
command[command.index(old_main)] = str(output / 'main.cpp.o')
exe = output / 'OpenSHSMStockAudioRefill'
command[command.index('-o') + 1] = str(exe)
assert command == build['linkCommand']
assert sha(exe) == build['executableSha256']
component_path = output / 'component-verification.json'
component = json.loads(component_path.read_text())
assert component['buildSha256'] == sha(build_path)
assert component['result'] == 'AUDIO_REFILL_VALID_PCM_CAP_BOUNDS_ERRORS_PASS9'
run_path = root / 'headless-sc-pc-headless-windowed-audio-refill-live-result.json'
run = json.loads(run_path.read_text())
assert run['terminalReturncode'] == 0 and run['deadlineReached'] and not run['logLimitReached']
assert run['windowed'] and run['capture'] and run['dspSupply'] and run['wallTimebase']
assert run['executableSha256'] == sha(exe)
log = root / 'headless-sc-pc-headless-windowed-audio-refill-live.log'
assert sha(log) == run['logSha256']
text = log.read_text()
def rows(prefix, fields):
    pattern = r'^\[' + prefix + r'\] ' + ' '.join(key + r'=(\d+)' for key in fields) + r'$'
    parsed = [dict(zip(fields, map(int, match.groups()))) for match in re.finditer(pattern, text, re.M)]
    total = sum(line.startswith('[' + prefix + '] ') for line in text.splitlines())
    return parsed, total - len(parsed)

adma_fields = ['wallUs', 'input32', 'input48', 'accepted', 'dropped', 'flushAccepted', 'flushDropped',
    'supplied', 'requested', 'short', 'ring', 'tbFirst', 'tbLast', 'tbFrequency', 'tbWallUs']
adma, adma_excluded = rows('ADMAAccounting', adma_fields)
refill, refill_excluded = rows('AudioRefill', ['wallUs', 'pulls', 'supplied', 'queued', 'empty',
    'errors', 'limited', 'before', 'after'])
assert adma and refill
for row in adma:
    assert row['accepted'] - row['supplied'] == row['ring']
    if not row['input48']:
        assert row['input32'] == row['accepted'] + row['dropped']
for row in refill:
    assert row['supplied'] == row['queued'] and row['errors'] == 0
    assert row['after'] <= 8192
for group, fields in [(adma, adma_fields[:10]), (refill, ['wallUs', 'pulls', 'supplied', 'queued', 'empty', 'errors', 'limited'])]:
    for previous, current in zip(group, group[1:]):
        assert all(current[key] >= previous[key] for key in fields)
last = adma[-1]
ratio = (last['tbLast'] - last['tbFirst']) * 1000000 / (last['tbFrequency'] * last['tbWallUs'])
assert 0.99 < ratio < 1.01
av_pattern = (r'^\[AVDebug\] seconds=([\d.]+) present=(\d+) gx=(\d+) queueMinBytes=(\d+) '
    r'empty=(\d+) pulls=(\d+) suppliedFrames=(\d+) short=(\d+) errors=(\d+)$')
av = [dict(zip(['seconds', 'present', 'gx', 'queueMinBytes', 'empty', 'pulls', 'suppliedFrames', 'short', 'errors'],
    [float(match[0]), *map(int, match[1:])])) for match in re.findall(av_pattern, text, re.M)]
assert av
captures = {}
for bmp in root.glob('headless-sc-pc-audio-refill-live-efb_debug_*.bmp'):
    png = bmp.with_suffix('.display.png')
    with Image.open(bmp) as image:
        rgb = image.convert('RGB')
        rgb.save(png)
        with Image.open(png) as check:
            assert check.convert('RGB').tobytes() == rgb.tobytes()
    captures[bmp.stem] = {'bmpSha256': sha(bmp), 'pngSha256': sha(png)}
assert captures
report = {'result': 'AUDIO_REFILL_WIRING_BALANCE_LIVE_AUDITED_NOT_AUDIO_ACCEPTED',
    'buildSha256': sha(build_path), 'componentSha256': sha(component_path), 'runSha256': sha(run_path),
    'logSha256': sha(log), 'auditorSha256': sha(Path(__file__)), 'admaRows': adma, 'refillRows': refill,
    'excludedNondecimalOrInterleaved': {'adma': adma_excluded, 'refill': refill_excluded},
    'lastAdma': last, 'lastRefill': refill[-1], 'configuredTbToWallRatio': ratio,
    'maxRingFrames': max(row['ring'] for row in adma), 'avRows': av,
    'avEmptyQueueSamples': sum(row['empty'] for row in av), 'captures': captures,
    'limits': ['Source/link reversal pins main-only consumer; actual runtime/75guest objects retained.',
        'Counters from ADMA and consumer have different report epochs, not cross-subtracted.',
        'Only complete decimal rows validated; original log has stream-format contamination/interleaving.',
        'Actual ring losses/empty queue samples remain; not proof of audible fix or causal attribution to captures.',
        'No original Wii/full-game speed, controlled FPS comparison, profile/story/controller or release acceptance.']}
(output / 'live-audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(report['result'])
print(json.dumps({key: report[key] for key in ['lastAdma', 'lastRefill', 'maxRingFrames',
    'configuredTbToWallRatio', 'avEmptyQueueSamples', 'excludedNondecimalOrInterleaved']}, indent=2))

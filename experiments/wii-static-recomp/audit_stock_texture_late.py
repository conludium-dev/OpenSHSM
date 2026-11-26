"""Audit owned late texture before/post bytes alongside current movie/SDK evidence."""
from pathlib import Path
import argparse
import collections
import hashlib
import json
import re
from PIL import Image

base = Path('experiments/wii-static-recomp/audit_stock_dispatch_select.py')
script = base.read_text()
script = script.replace('window-dispatch-select', 'window-texture-late')
script = script.replace('dispatch-select', 'texture-late')
script = script.replace('window-vi-busy-latch/build.json', 'window-dispatch-select/build.json')
script = script.replace('window-vi-busy-latch/live-input-audit.json', 'window-dispatch-select/live-input-audit.json')
script = script.replace('headless-windowed-vi-busy-latch', 'headless-windowed-dispatch-select')
script = script.replace('CURRENT_TIMER_ONLY_LATE_PACKET_VISUAL_AUDIO_AUDITED', 'DISPATCH_SELECT_LIVE_PARENT_PACKETS_SDK_AUDIO_AUDITED')
script = script.replace('DISPATCH_SELECT_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_EQUAL',
    'TEXTURE_LATE_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_EQUAL')
scope = {'__file__': __file__}
parser = argparse.ArgumentParser()
parser.add_argument('--artifacts', type=Path, required=True)
options = parser.parse_args()
artifacts = options.artifacts.resolve()
assert artifacts.parent == Path('/private/tmp') and re.fullmatch(r'openshsm-run-[A-Za-z0-9_-]+', artifacts.name)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
run_path = artifacts / 'headless-sc-pc-headless-windowed-texture-late-result.json'
run = json.loads(run_path.read_text())
timing = artifacts / 'headless-sc-pc-texture-late-movie-timing.jsonl'
movie_missing = timing.stat().st_size == 0
if not movie_missing:
    exec(compile(script, str(base), 'exec'), scope)
    packet = scope['packet']
    run = scope['scope']['run']
    artifacts = scope['scope']['artifacts']
else:
    assert run['terminalReturncode'] == 0 and run['deadlineReached'] and run['temporaryEvidence']
    assert Path(run['artifactDirectory']).resolve() == artifacts
    log = artifacts / 'headless-sc-pc-headless-windowed-texture-late.log'
    assert sha(log) == run['logSha256']
    phase = Path('experiments/wii-static-recomp/audit_stock_live_phases.py').read_text()
    phase_scope = {'re': re, 'text': log.read_text(), 'args': type('Options', (), {'timer_only': True})()}
    exec(compile(phase[phase.index("fields = ['hostUs'"):phase.index('movie_path = root /')], '<actual-phases>', 'exec'), phase_scope)
    build_path = Path('work/private-game/static-recomp/stock-baseline/window-texture-late/build.json')
    build = json.loads(build_path.read_text())
    component_path = build_path.parent / 'component-verification.json'
    component = json.loads(component_path.read_text())
    assert component['buildSha256'] == sha(build_path)
    assert component['result'] == 'TEXTURE_LATE_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_EQUAL'
    assert sha(Path(build['executablePath'])) == build['executableSha256'] == run['executableSha256']
    packet = {'runSha256': sha(run_path), 'currentPhaseSummary': phase_scope['summary']}
    scope['scope'] = {'sha': sha}
assert run['textureObserve'] and run['textureCoherence'] and run['textureCaptureAfterMs'] == 140000
directory = Path(run['textureDirectory'])
assert directory.parent.resolve() == artifacts.resolve()
files = list(directory.iterdir())
payload_bytes = sum(path.stat().st_size for path in files if path.suffix in ('.raw', '.rgba', '.tlut'))
assert payload_bytes <= 96 * 1024 * 1024
keys = collections.Counter()
records = []
def fnv(data):
    value = 2166136261
    for byte in data:
        value = ((value ^ byte) * 16777619) & 0xFFFFFFFF
    return value
for metadata in sorted(directory.glob('texture-*.txt')):
    if metadata.name.endswith('.coherence.txt'):
        continue
    fields = list(map(int, metadata.read_text().splitlines()[0].split()))
    assert len(fields) == 10
    sequence, address, width, height, fmt, tlut_offset, tlut_fmt, cache_hash, size, tev = fields[:10]
    prefix = metadata.with_suffix('')
    raw_path, rgba_path = Path(str(prefix) + '.raw'), Path(str(prefix) + '.rgba')
    raw = raw_path.read_bytes()
    assert len(raw) == size and rgba_path.stat().st_size == width * height * 4
    keys[(address, width, height, fmt)] += 1
    assert keys[(address, width, height, fmt)] <= 2
    coherence = Path(str(prefix) + '.coherence.txt')
    if coherence.exists():
        before_path = Path(str(prefix) + '.before.raw')
        before = before_path.read_bytes()
        assert len(before) == len(raw)
        values = list(map(int, coherence.read_text().split()))
        assert len(values) == 8 and values[1] >= values[0] and values[4] == 1
        assert fnv(before) == values[2] and fnv(raw) == values[3]
        differences = [index for index, pair in enumerate(zip(before, raw)) if pair[0] != pair[1]]
        assert len(differences) == values[5]
        assert values[6] == (differences[0] if differences else len(raw))
        if differences:
            assert values[7] == differences[-1]
        records.append({'sequence': sequence, 'address': address, 'width': width, 'height': height,
            'format': fmt, 'beforeUs': values[0], 'afterUs': values[1], 'changedBytes': len(differences),
            'beforePath': str(before_path), 'beforeSha256': scope['scope']['sha'](before_path),
            'rawPath': str(raw_path), 'rawSha256': scope['scope']['sha'](raw_path),
            'rgbaPath': str(rgba_path), 'rgbaSha256': scope['scope']['sha'](rgba_path)})
        if fmt == 1:
            rgba = rgba_path.read_bytes()
            matches = collections.Counter()
            changed_rows = []
            neither_rows = []
            for y in range(height):
                for x in range(width):
                    offset = ((y // 4) * ((width + 7) // 8) + x // 8) * 32 + (y % 4) * 8 + x % 8
                    value = rgba[(y * width + x) * 4]
                    assert rgba[(y * width + x) * 4:(y * width + x) * 4 + 4] == bytes([value]) * 4
                    equal_before, equal_after = value == before[offset], value == raw[offset]
                    matches['both' if equal_before and equal_after else 'beforeOnly' if equal_before
                        else 'afterOnly' if equal_after else 'neither'] += 1
                    if before[offset] != raw[offset]:
                        changed_rows.append(y)
                    if not equal_before and not equal_after:
                        neither_rows.append(y)
            records[-1]['decodedI8Comparison'] = dict(matches)
            records[-1]['sourceChangedRowRange'] = [min(changed_rows), max(changed_rows)] if changed_rows else None
            records[-1]['decodedNeitherRowRange'] = [min(neither_rows), max(neither_rows)] if neither_rows else None
assert records and len(keys) <= 256 and sum(keys.values()) <= 128
report = {'result': 'OWNED_LATE_TEXTURE_COHERENCE_BYTES_AUDITED',
    'runSha256': packet['runSha256'], 'payloadBytes': payload_bytes, 'captures': sum(keys.values()),
    'pairedCaptures': len(records), 'changedPairs': sum(row['changedBytes'] != 0 for row in records),
    'records': records, 'phaseSummary': packet['currentPhaseSummary'],
    'movieEvidenceMissing': movie_missing,
    'decodedMixedPairs': sum(bool(row.get('decodedI8Comparison', {}).get('beforeOnly')) and
        bool(row.get('decodedI8Comparison', {}).get('afterOnly')) for row in records),
    'limits': ['Direct unsynchronized copies can tear; equal pairs do not prove whole decode or producer stability.',
        'Texture cache misses only/perkey2/128 caps; sparse captured textures may not coincide with bad EFB frame.',
        'Diagnostics add CPU/file IO cost, not a performance candidate or FPS improvement claim.']}
if movie_missing:
    report['limits'].append('Movie delay was never reached: no new movie packets or source-position slope verified in this run. Texture and movie gate origins differ.')
captures = []
capture_prefix = Path(run['capturePrefix'])
assert capture_prefix.parent.parent == Path('/private/tmp') and capture_prefix.parent.name.startswith('openshsm-captures-')
for bmp in sorted(capture_prefix.parent.glob(capture_prefix.name + '_debug_*.bmp')):
    png = bmp.with_suffix('.display.png')
    with Image.open(bmp) as original:
        rgb = original.convert('RGB')
        rgb.save(png)
        with Image.open(png) as check:
            assert check.convert('RGB').tobytes() == rgb.tobytes()
    captures.append({'bmpPath': str(bmp), 'bmpSha256': sha(bmp), 'displayPath': str(png), 'displaySha256': sha(png)})
report['imageCaptures'] = captures
report['auditorSha256'] = sha(Path(__file__))
path = artifacts / 'texture-coherence-audit.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], {'captures': report['captures'], 'pairs': len(records), 'changedPairs': report['changedPairs']})

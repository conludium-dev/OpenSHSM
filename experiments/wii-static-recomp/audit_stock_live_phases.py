"""Correlate current host phases, sampled original SDK retraces and existing movie boundaries."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import statistics
import struct
from PIL import Image
from stock_vi_path_observation import adapt_vi_path

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
parser = argparse.ArgumentParser()
parser.add_argument('--timer-only', action='store_true')
args = parser.parse_args()
output = root / ('window-vi-timer' if args.timer_only else 'window-live-phases')
tag = 'vi-timer' if args.timer_only else 'live-phases'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
if args.timer_only:
    original = Path(build['mainOriginalPath'])
    assert sha(original) == build['mainOriginalSha256']
    before, after = build['patch']
    assert original.read_text().count(before) == 1
    assert original.read_text().replace(before, after) == (output / 'main.cpp').read_text()
    parent_path = root / 'window-live-phases/build.json'
    assert sha(parent_path) == build['parentBuildSha256']
    vi_build = json.loads(parent_path.read_text())
    vi_source = root / 'window-live-phases/output_39.cpp'
else:
    expected = Path(build['mainOriginalPath']).read_text()
    assert sha(Path(build['mainOriginalPath'])) == build['mainOriginalSha256']
    for before, after in build['patches']:
        assert expected.count(before) == 1
        expected = expected.replace(before, after)
    assert '#include "stock_host_phases.h"\n' + expected == (output / 'main.cpp').read_text()
    vi_build = build
    vi_source = output / 'output_39.cpp'
vi_original = Path(vi_build['viOriginalPath'])
assert sha(vi_original) == vi_build['viOriginalSha256']
vi, stages, calls = adapt_vi_path(vi_original.read_text())
for before, after in vi_build['viPatches']:
    assert vi.count(before) == 1
    vi = vi.replace(before, after)
assert vi == vi_source.read_text()
assert stages == tuple(vi_build['stages']) and calls == vi_build['observedCalls']
markers = lambda text: re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', text)
assert markers(vi) == markers(vi_original.read_text())
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
layout = struct.unpack('>64I', dol[:256])
sdk_words = 0
for address, word in markers(vi):
    address = int(address, 16)
    if 0x802280F0 <= address < 0x80228900:
        section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
        assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == int(word, 16)
        sdk_words += 1
assert sdk_words
exe = output / ('OpenSHSMStockVITimer' if args.timer_only else 'OpenSHSMStockLivePhases')
assert sha(exe) == build['executableSha256']
run_path = root / f'headless-sc-pc-headless-windowed-{tag}-result.json'
log = root / f'headless-sc-pc-headless-windowed-{tag}.log'
run = json.loads(run_path.read_text())
assert run['terminalReturncode'] == 0 and run['deadlineReached'] and run['movieTiming']
assert run['windowed'] and run['capture'] and run['executableSha256'] == sha(exe)
assert sha(log) == run['logSha256']
text = log.read_text()
fields = ['hostUs', 'elapsedUs', 'loops', 'gx', 'publications', 'pendingSamples', 'inputNs', 'xfbNs',
    'gxNs', 'statsNs', 'blitNs', 'swapNs', 'audioNs', 'restNs', 'sleepNs', 'final']
host = [dict(zip(fields, map(int, row))) for row in re.findall(
    r'^\[HostPhases\] ' + ' '.join(key + r'=(\d+)' for key in fields) + r'$', text, re.M)]
assert host and host[-1]['final'] == 1
active = [row for row in host if row['loops'] and row['gx'] and row['hostUs'] >= host[-1]['hostUs'] - 30000000]
assert active
for row in host:
    assert row['publications'] == (0 if args.timer_only else row['loops'])
    assert row['pendingSamples'] <= row['publications']
duration = sum(row['elapsedUs'] for row in active)
loops = sum(row['loops'] for row in active)
summary = {'intervals': len(active), 'loops': loops, 'elapsedUs': duration,
    'hostLoopsPerSecond': loops * 1000000 / duration,
    'gxBatchesPerSecond': sum(row['gx'] for row in active) * 1000000 / duration,
    'pendingStateSamples': sum(row['pendingSamples'] for row in active),
    'meanPhaseMs': {key: sum(row[key] for row in active) / (loops * 1000000) for key in fields if key.endswith('Ns')}}
vi_rows = [{'hostUs': int(ns) // 1000, 'stage': int(stage, 16), 'counter': int(counter, 16)}
    for ns, stage, counter in re.findall(r'\[VIPath\] ns=(\d+) stage=([0-9a-f]+) yield=0 .*? counter=([0-9a-f]+) ', text)]
vi_active = [row for row in vi_rows if row['stage'] == 0x8022824C and
    active[0]['hostUs'] - active[0]['elapsedUs'] <= row['hostUs'] <= active[-1]['hostUs']]
assert len(vi_active) >= 2
delta = (vi_active[-1]['counter'] - vi_active[0]['counter']) & 0xFFFFFFFF
elapsed = vi_active[-1]['hostUs'] - vi_active[0]['hostUs']
assert elapsed > 0 and delta < 100000
summary['sdkRetracesPerSecond'] = delta * 1000000 / elapsed
movie_path = root / f'headless-sc-pc-{tag}-movie-timing.jsonl'
movie = [json.loads(line) for line in movie_path.read_text().splitlines()]
assert movie and len(movie) <= 4096 and all(row['serial'] == i for i, row in enumerate(movie))
pairs = {0x80209D80: 0x8020A044, 0x8009C5E0: 0x8009C5E4,
    0x8009C624: 0x8009C628, 0x8009B760: 0x8009B76C}
pending, completed, displaced, unpaired = {}, [], [], []
for row in movie:
    key = (pairs.get(row['site'], row['site']), row['thread'], row['sp'])
    if row['site'] in pairs:
        if key in pending: displaced.append(pending[key])
        pending[key] = row
    else:
        begin = pending.pop(key, None)
        if begin is None:
            unpaired.append(row)
        elif begin['site'] == 0x80209D80 and begin['lr'] != row['lr']:
            unpaired.extend([begin, row])
        else:
            completed.append({'begin': begin, 'end': row, 'elapsedUs': row['hostUs'] - begin['hostUs']})
decode = [row['elapsedUs'] for row in completed if row['begin']['site'] == 0x80209D80]
assert decode
captures = {}
for bmp in root.glob(f'headless-sc-pc-{tag}-efb_debug_*.bmp'):
    png = bmp.with_suffix('.display.png')
    with Image.open(bmp) as image:
        rgb = image.convert('RGB')
        rgb.save(png)
        with Image.open(png) as check: assert check.convert('RGB').tobytes() == rgb.tobytes()
    captures[bmp.stem] = {'bmpSha256': sha(bmp), 'pngSha256': sha(png)}
report = {'result': 'LIVE_HOST_VI_MOVIE_PHASES_AUDITED', 'buildSha256': sha(build_path),
    'runSha256': sha(run_path), 'auditorSha256': sha(Path(__file__)), 'sdkWordsChecked': sdk_words,
    'hostRows': host, 'viRows': vi_rows, 'selectedLast30Seconds': summary,
    'movieRecords': len(movie), 'movieCapReached': len(movie) == 4096, 'movieSha256': sha(movie_path),
    'decoderPairs': len(decode), 'decoderMedianInclusiveUs': statistics.median(decode),
    'movieCompleted': completed, 'movieDisplaced': displaced, 'movieUnpaired': unpaired, 'moviePending': list(pending.values()),
    'captures': captures, 'limits': ['Read-only observed rates, not a controlled pacing change or original Wii clock proof.',
        'Last30s selection may differ from bounded movie-cap coverage; decoder timings include IRQ/scheduling.',
        'Host phase sums omit observer report overhead; pending samples not precise lost retraces.',
        'No full story/profile/save/controller/audio/visual acceptance or release promotion.']}
(output / 'live-audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('LIVE_HOST_VI_MOVIE_PHASES_AUDITED')
print(json.dumps({'selectedLast30Seconds': summary, 'movieRecords': len(movie),
    'decoderPairs': len(decode), 'decoderMedianInclusiveUs': statistics.median(decode)}, indent=2))

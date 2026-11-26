"""Pair actual original instruction-boundary events; host latency, not FPS/GPU timing."""
from pathlib import Path
import argparse
import hashlib
import json
import statistics

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
parser = argparse.ArgumentParser()
parser.add_argument('--tag', default='movie-timing-first')
parser.add_argument('--build', choices=('headless-movie-timing', 'headless-constant-fp', 'headless-psq-scale'), default='headless-movie-timing')
args = parser.parse_args()
assert args.tag.replace('-', '').isalnum()
output = root / args.build
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, expected in {**build['dependencies'], **build['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected, path
exe = Path(build['linkCommand'][build['linkCommand'].index('-o') + 1])
assert sha(exe) == build['executableSha256']
archive = next(Path(arg) for arg in build['linkCommand'] if Path(arg).name == 'libnwiiruntime.a')
assert sha(archive) == build['archiveSha256']
for unit, change in build.get('changes', {'37': build}).items():
    assert sha(output / f'output_{unit}.cpp') == change['sourceSha256']
if args.build == 'headless-constant-fp':
    from stock_constant_fp_patch import specialize
    parent_path = root / 'headless-movie-timing/build.json'
    parent = json.loads(parent_path.read_text())
    assert sha(parent_path) == build['baseBuildSha256']
    expected = list(parent['linkCommand'])
    old = next(Path(arg) for arg in expected if Path(arg).name == 'output_37.cpp.o')
    expected[expected.index(str(old))] = str(output / 'output_37.cpp.o')
    expected[expected.index('-o') + 1] = str(exe)
    assert expected == build['linkCommand']
    header, source, sites = specialize(Path('experiments/wii-static-recomp/stock_fp_unavailable.h').read_text(),
        old.with_suffix('').read_text(), Path('work/private-game/disc/DATA/sys/main.dol').read_bytes())
    assert header == (output / 'constant_fp_guard.h').read_text()
    assert source == (output / 'output_37.cpp').read_text() and sites == build['sites']
label = 'headless'
run_path = root / f'headless-sc-pc-{label}-{args.tag}-result.json'
run = json.loads(run_path.read_text())
assert run['result'] == 'BOUNDED_STOCK_RUN_COMPLETE' and run.get('movieTiming') is not False
assert run['executableSha256'] == sha(exe) and run['experimentalExecutable'] == str(exe)
assert not run['windowed']
log = root / f'headless-sc-pc-{label}-{args.tag}.log'
assert run['logSha256'] == sha(log)
capture = root / f'headless-sc-pc-{args.tag}-movie-timing.jsonl'
rows = [json.loads(line) for line in capture.read_text().splitlines()] if capture.exists() else []
assert run.get('movieTiming') is True or rows, 'No evidence that timing was enabled'
assert len(rows) <= 4096 and all(row['serial'] == i for i, row in enumerate(rows))
assert all(rows[i]['hostUs'] <= rows[i + 1]['hostUs'] for i in range(len(rows) - 1))
pairs = {0x80209D80: 0x8020A044, 0x8009C5E0: 0x8009C5E4,
         0x8009C624: 0x8009C628, 0x8009B760: 0x8009B76C}
pending = {}
completed, displaced, unpaired = [], [], []
for row in rows:
    site = row['site']
    if site in pairs:
        key = (pairs[site], row['thread'], row['sp'])
        if key in pending:
            displaced.append(pending[key])
        pending[key] = row
    else:
        key = (site, row['thread'], row['sp'])
        start = pending.pop(key, None)
        if start is None:
            unpaired.append(row)
            continue
        if start['site'] == 0x80209D80 and start['lr'] != row['lr']:
            unpaired.extend([start, row])
            continue
        completed.append({'begin': start, 'end': row, 'elapsedUs': row['hostUs'] - start['hostUs']})
summary = {}
for site in pairs:
    subset = [pair for pair in completed if pair['begin']['site'] == site]
    times = [pair['elapsedUs'] for pair in subset]
    summary[hex(site)] = {'pairs': len(times), 'medianUs': statistics.median(times) if times else None,
        'minUs': min(times) if times else None, 'maxUs': max(times) if times else None}
movie = [pair for pair in completed if pair['begin']['site'] == 0x80209D80 and pair['begin']['lr'] == 0x8009C5E4]
movie_times = [pair['elapsedUs'] for pair in movie]
summary['movieDecoder'] = {'pairs': len(movie), 'medianUs': statistics.median(movie_times) if movie else None,
    'minUs': min(movie_times) if movie else None, 'maxUs': max(movie_times) if movie else None,
    'returns': sorted(set(pair['end']['r3'] for pair in movie))}
report = {'result': 'MOVIE_TIMING_CAPTURE_AUDITED' if rows else 'NO_MOVIE_TIMING_RECORDS_NO_LATENCY_RESULT',
    'buildSha256': sha(build_path), 'runSha256': sha(run_path), 'movieTimingFlagRecorded': run.get('movieTiming'),
    'captureSha256': sha(capture) if capture.exists() else None, 'logSha256': sha(log), 'recipeSha256': sha(Path(__file__).resolve()),
    'records': len(rows), 'capReached': len(rows) == 4096, 'summary': summary, 'completed': completed,
    'displaced': displaced, 'unpairedEnds': unpaired, 'pending': list(pending.values()),
    'limits': ['Boundary wall time includes interruptions/scheduling/waits/observer overhead, not decoder CPU-exclusive cost.',
        'D4 context and SP pair keys; displaced/unpaired records retained, not silently merged.',
        'No rendered/presentation FPS, GPU time, visual acceptance or original Wii timing oracle.']}
(output / f'{args.tag}-timing-audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'records': len(rows), 'summary': summary, 'displaced': len(displaced),
    'unpairedEnds': len(unpaired), 'pending': len(pending)}, indent=2))

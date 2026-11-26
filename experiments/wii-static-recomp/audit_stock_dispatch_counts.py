"""Attribute actual master routing counts to observed decoder intervals, not interpreter CPU time."""
from pathlib import Path
import hashlib
import json
import statistics

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-dispatch-counts'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
master = (output / 'fixed.cpp').read_text()
for before, after in reversed(build['masterPatches']):
    master = master.replace(after, before, 1)
assert master.replace(build['masterHelper'], '', 1) == Path(build['masterOriginalPath']).read_text()
assert sha(output / 'fixed.cpp.o') == build['masterObjectSha256']
component_path = output / 'component-verification.json'
component = json.loads(component_path.read_text())
assert component['result'] == 'DISPATCH_COUNTER_OBSERVER_FRAME_STATE_IDENTICAL3'
assert component['buildSha256'] == sha(build_path)
run_path = root / 'headless-sc-pc-headless-windowed-dispatch-counts-result.json'
run = json.loads(run_path.read_text())
exe = output / 'OpenSHSMStockDispatchCounts'
assert run['executableSha256'] == sha(exe) == build['executableSha256']
assert run['terminalReturncode'] == 0 and run['deadlineReached'] and not run['logLimitReached']
assert run['movieTiming'] and run['wallTimebase'] and run['windowed']
log = root / 'headless-sc-pc-headless-windowed-dispatch-counts.log'
assert sha(log) == run['logSha256']
timing = root / 'headless-sc-pc-dispatch-counts-movie-timing.jsonl'
rows = [json.loads(line) for line in timing.read_text().splitlines()]
assert rows and len(rows) <= 4096
keys = ['exact', 'bounds', 'interpreter', 'boundsIterations', 'exceptions']
assert all(row['serial'] == i for i, row in enumerate(rows))
assert all(all(a[key] <= b[key] for key in keys) for a, b in zip(rows, rows[1:]))
pending, decode, displaced, unpaired = {}, [], [], []
for row in rows:
    if row['site'] not in (0x80209D80, 0x8020A044): continue
    key = (row['thread'], row['sp'])
    if row['site'] == 0x80209D80:
        if key in pending: displaced.append(pending[key])
        pending[key] = row
    else:
        begin = pending.pop(key, None)
        if begin is None: unpaired.append(row); continue
        if begin['lr'] != row['lr']: unpaired.extend([begin, row]); continue
        counts = {key: row[key] - begin[key] for key in keys}
        assert all(value >= 0 for value in counts.values())
        decode.append({'begin': begin, 'end': row, 'wallUs': row['hostUs'] - begin['hostUs'],
            'hostThreadCpuUs': row['hostThreadCpuUs'] - begin['hostThreadCpuUs'], 'counts': counts})
assert decode
totals = {key: sum(row['counts'][key] for row in decode) for key in keys}
summary = {'decoderPairs': len(decode), 'medianWallUs': statistics.median(row['wallUs'] for row in decode),
    'sumCountsDuringDecoder': totals,
    'medianCountsPerDecoder': {key: statistics.median(row['counts'][key] for row in decode) for key in keys},
    'lastCounters': {key: rows[-1][key] for key in keys},
    'returnValues': sorted(set(row['end']['r3'] for row in decode))}
(output / 'live-audit.json').write_text(json.dumps({'result': 'MASTER_ROUTING_COUNTS_DURING_DECODER_AUDITED',
    'buildSha256': sha(build_path), 'componentSha256': sha(component_path), 'runSha256': sha(run_path),
    'timingSha256': sha(timing), 'auditorSha256': sha(Path(__file__)), 'records': len(rows),
    'capReached': len(rows) == 4096, 'summary': summary, 'decoderPairs': decode,
    'displaced': displaced, 'unpaired': unpaired, 'pending': list(pending.values()),
    'limits': ['Counts only run_game branches, not nested interpreter or sdk_enable_dispatch calls.',
        'Counter work especially boundsIterations changes runtime cost; counts are not measured CPU time fractions.',
        'Decoder interval includes other guest threads/IRQ/runtime; source-frame fidelity proof separate.',
        'No visual/audio/Wii/whole-game FPS/controller/save/story acceptance or default promotion.']}, indent=2) + '\n')
print('MASTER_ROUTING_COUNTS_DURING_DECODER_AUDITED')
print(json.dumps(summary, indent=2))

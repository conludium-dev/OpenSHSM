"""Audit the counter-free live routing candidate; live-frame distributions are not identical packets."""
from pathlib import Path
import hashlib
import json
import statistics

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-bounds-lookup'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
master = (output / 'fixed.cpp').read_text()
before, after = build['masterPatch']
assert master.replace(after, before, 1).replace(build['declaration'], '', 1) == Path(build['masterOriginalPath']).read_text()
assert sha(output / 'fixed.cpp.o') == build['masterObjectSha256']
assert sha(output / 'bounds.cpp.o') == build['lookupObjectSha256']
component_path = output / 'component-verification.json'
component = json.loads(component_path.read_text())
assert component['result'] == 'BOUNDS_LOOKUP_FRAME_STATE_IDENTICAL3'
assert component['buildSha256'] == sha(build_path)
routing_path = output / 'routing-verification.json'
assert component['routingProofSha256'] == sha(routing_path)
routing = json.loads(routing_path.read_text())
assert routing['result'] == 'ALL_UINT32_PARTITIONS_ROUTING_EQUAL'
assert routing['buildSha256'] == sha(build_path)
assert routing['verifierSha256'] == component['verifierSha256'] == sha(Path('experiments/wii-static-recomp/verify_stock_bounds_lookup.py'))
run_path = root / 'headless-sc-pc-headless-windowed-bounds-lookup-result.json'
run = json.loads(run_path.read_text())
assert run['executableSha256'] == sha(output / 'OpenSHSMStockBoundsLookup') == build['executableSha256']
assert run['terminalReturncode'] == 0 and run['deadlineReached'] and not run['logLimitReached']
assert run['movieTiming'] and run['wallTimebase'] and run['windowed']
log = root / 'headless-sc-pc-headless-windowed-bounds-lookup.log'
assert sha(log) == run['logSha256']
timing = root / 'headless-sc-pc-bounds-lookup-movie-timing.jsonl'
rows = [json.loads(line) for line in timing.read_text().splitlines()]
assert rows and len(rows) <= 4096 and all(row['serial'] == i for i, row in enumerate(rows))
assert all(row['hostThreadCpuUs'] >= 0 and 'boundsIterations' not in row for row in rows)
assert all(a['hostUs'] <= b['hostUs'] and a['hostThreadCpuUs'] <= b['hostThreadCpuUs'] for a, b in zip(rows, rows[1:]))
pending, decode, displaced, unpaired = {}, [], [], []
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
        wall, cpu = row['hostUs'] - begin['hostUs'], row['hostThreadCpuUs'] - begin['hostThreadCpuUs']
        assert wall >= 0 and cpu >= 0 and cpu <= wall + 1000
        decode.append({'begin': begin, 'end': row, 'wallUs': wall, 'hostThreadCpuUs': cpu})
assert decode
summary = {'decoderPairs': len(decode), 'medianWallUs': statistics.median(row['wallUs'] for row in decode),
    'medianHostThreadCpuUs': statistics.median(row['hostThreadCpuUs'] for row in decode),
    'returnValues': sorted(set(row['end']['r3'] for row in decode)),
    'callerLRs': sorted(set(row['begin']['lr'] for row in decode))}
(output / 'live-audit.json').write_text(json.dumps({
    'result': 'COUNTER_FREE_BOUNDS_LOOKUP_LIVE_AUDITED', 'buildSha256': sha(build_path),
    'routingProofSha256': sha(routing_path), 'componentSha256': sha(component_path),
    'runSha256': sha(run_path), 'timingSha256': sha(timing), 'auditorSha256': sha(Path(__file__)),
    'records': len(rows), 'capReached': len(rows) == 4096, 'summary': summary, 'decoderPairs': decode,
    'displaced': displaced, 'unpaired': unpaired, 'pending': list(pending.values()),
    'limits': ['Counter-free master; unchanged existing movie CPU-time observer retained.',
        'Different live frames/IRQ/timing histories: not an identical-packet controlled benchmark.',
        'Host CPU interval includes other guest threads/IRQs; GX counts are not unique movie frame FPS.',
        'No new visual/audio/user/hardware/profile/save/controller acceptance; default promotion deferred.']}, indent=2) + '\n')
print('COUNTER_FREE_BOUNDS_LOOKUP_LIVE_AUDITED')
print(json.dumps(summary, indent=2))

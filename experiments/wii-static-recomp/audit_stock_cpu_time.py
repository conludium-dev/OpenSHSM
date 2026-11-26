"""Compare host PPC-thread CPU occupancy to wall intervals; do not call it decoder-exclusive CPU time."""
from pathlib import Path
import hashlib
import json
import statistics

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-cpu-time'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
for unit, change in build['changes'].items():
    assert (output / f'output_{unit}.cpp').read_bytes() == Path(change['originalPath']).read_bytes()
    assert sha(output / f'output_{unit}.cpp.o') == change['objectSha256']
component_path = output / 'component-verification.json'
component = json.loads(component_path.read_text())
assert component['buildSha256'] == sha(build_path) and component['result'] == 'CPU_TIME_OBSERVER_FRAME_STATE_IDENTICAL3'
run_path = root / 'headless-sc-pc-headless-windowed-cpu-time-result.json'
run = json.loads(run_path.read_text())
exe = output / 'OpenSHSMStockCPUTime'
assert run['executableSha256'] == sha(exe) == build['executableSha256']
assert run['terminalReturncode'] == 0 and run['deadlineReached'] and not run['logLimitReached']
assert run['movieTiming'] and run['wallTimebase'] and run['windowed']
log = root / 'headless-sc-pc-headless-windowed-cpu-time.log'
assert sha(log) == run['logSha256']
timing = root / 'headless-sc-pc-cpu-time-movie-timing.jsonl'
rows = [json.loads(line) for line in timing.read_text().splitlines()]
assert rows and len(rows) <= 4096 and all(row['serial'] == i for i, row in enumerate(rows))
assert all(row['hostThreadCpuUs'] >= 0 for row in rows)
assert all(a['hostUs'] <= b['hostUs'] and a['hostThreadCpuUs'] <= b['hostThreadCpuUs'] for a, b in zip(rows, rows[1:]))
pairs = {0x80209D80: 0x8020A044, 0x8009C5E0: 0x8009C5E4,
    0x8009C624: 0x8009C628, 0x8009B760: 0x8009B76C}
pending, completed, displaced, unpaired = {}, [], [], []
for row in rows:
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
            wall = row['hostUs'] - begin['hostUs']
            cpu = row['hostThreadCpuUs'] - begin['hostThreadCpuUs']
            assert wall >= 0 and cpu >= 0 and cpu <= wall + 1000
            completed.append({'begin': begin, 'end': row, 'wallUs': wall, 'hostThreadCpuUs': cpu})
decode = [row for row in completed if row['begin']['site'] == 0x80209D80]
assert decode
summary = {'decoderPairs': len(decode), 'medianWallUs': statistics.median(row['wallUs'] for row in decode),
    'medianHostThreadCpuUs': statistics.median(row['hostThreadCpuUs'] for row in decode),
    'sumWallUs': sum(row['wallUs'] for row in decode), 'sumHostThreadCpuUs': sum(row['hostThreadCpuUs'] for row in decode),
    'returnValues': sorted(set(row['end']['r3'] for row in decode))}
summary['aggregateHostThreadCpuToWallRatio'] = summary['sumHostThreadCpuUs'] / summary['sumWallUs']
(output / 'live-audit.json').write_text(json.dumps({'result': 'ORIGINAL_MOVIE_HOST_THREAD_CPU_WALL_AUDITED',
    'buildSha256': sha(build_path), 'componentSha256': sha(component_path), 'runSha256': sha(run_path),
    'timingSha256': sha(timing), 'auditorSha256': sha(Path(__file__)), 'records': len(rows),
    'capReached': len(rows) == 4096, 'summary': summary, 'completed': completed, 'displaced': displaced,
    'unpaired': unpaired, 'pending': list(pending.values()),
    'limits': ['Host CPU time includes all guest threads/IRQs executing on the same emulator host thread.',
        'CPU/wall difference bounds host non-execution, not which original guest wait caused it.',
        'Median of different live frames not comparable to specific HM1PLY15 native fixture.',
        'No captured image/audio/hardware/whole-game speed/controller/save/story acceptance; diagnosis only.']}, indent=2) + '\n')
print('ORIGINAL_MOVIE_HOST_THREAD_CPU_WALL_AUDITED')
print(json.dumps(summary, indent=2))

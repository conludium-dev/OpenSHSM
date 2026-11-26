"""Prove observer derivation and same-frame YUV/selected CPU state while CPU-time recording is enabled."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-cpu-time'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
restored = (output / 'stock_movie_timing.h').read_text()
for before, after in reversed(build['headerPatches']):
    assert restored.count(after) == 1
    restored = restored.replace(after, before)
assert restored == Path('experiments/wii-static-recomp/stock_movie_timing.h').read_text()
for unit, change in build['changes'].items():
    assert sha(Path(change['originalPath'])) == change['originalSha256']
    assert (output / f'output_{unit}.cpp').read_bytes() == Path(change['originalPath']).read_bytes()
    assert sha(output / f'output_{unit}.cpp.o') == change['objectSha256']
parent_path = root / 'window-decoder-o3/build.json'
assert sha(parent_path) == build['parentBuildSha256']
proof = json.loads((root / 'window-decoder-o3/verification.json').read_text())
fixture_obj = root / 'window-decoder-o3/frame-probe.cpp.o'
assert sha(fixture_obj) == proof['fixtureObjectSha256']
temporary = Path(tempfile.mkdtemp(prefix='openshsm-cpu-time-probe-', dir='/private/tmp'))
exe = temporary / 'frame-probe'
command = list(build['linkCommand'])
main = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
command[command.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
command.insert(1, str(fixture_obj))
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
snapshot = root / 'headless-sc-pc-decoder-snapshot-retry-decoder-entry.bin'
packet = root / 'headless-thp-snapshot/hm1ply-frame15-replay/hm1ply-frame15.packet'
assert sha(snapshot) == proof['snapshotSha256'] and sha(packet) == proof['packetSha256']
reference_raw = root / 'window-decoder-o3/baseline-0.yuv'
reference_state = Path(str(reference_raw) + '.state')
rows = []
for iteration in range(3):
    raw = output / f'probe-{iteration}.yuv'
    timing = output / f'probe-{iteration}-timing.jsonl'
    assert not timing.exists()
    env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
    env['NWII_MOVIE_TIMING'] = str(timing)
    result = subprocess.run([str(exe), str(snapshot), str(raw), str(packet)], env=env,
        capture_output=True, text=True, timeout=30)
    log = output / f'probe-{iteration}.log'
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-2000:]
    assert raw.read_bytes() == reference_raw.read_bytes()
    assert Path(str(raw) + '.state').read_bytes() == reference_state.read_bytes()
    events = [json.loads(line) for line in timing.read_text().splitlines()]
    assert [row['site'] for row in events] == [0x80209D80, 0x8020A044]
    cpu = events[1]['hostThreadCpuUs'] - events[0]['hostThreadCpuUs']
    wall = events[1]['hostUs'] - events[0]['hostUs']
    assert events[0]['hostThreadCpuUs'] >= 0 and cpu > 0 and wall > 0 and cpu <= wall + 1000
    rows.append({'cpuUs': cpu, 'wallUs': wall, 'outputSha256': sha(raw),
        'stateSha256': sha(Path(str(raw) + '.state')), 'timingSha256': sha(timing), 'logSha256': sha(log)})
(output / 'component-verification.json').write_text(json.dumps({'result': 'CPU_TIME_OBSERVER_FRAME_STATE_IDENTICAL3',
    'buildSha256': sha(build_path), 'executablePath': str(exe), 'executableSha256': sha(exe),
    'fixtureObjectSha256': sha(fixture_obj), 'verifierSha256': sha(Path(__file__)), 'rows': rows,
    'limits': ['Observer enabled; same owned complete frame exact YUV/selected final PPC registers/inst_count.',
        'Host CPU-time clock returns positive supported monotonic data; not decoder-exclusive with guest preemption.',
        'One fixture/frame, not complete Wii/hardware/live IRQ/GUI/audio acceptance; temporary testEXE off Data.']}, indent=2) + '\n')
print('CPU_TIME_OBSERVER_FRAME_STATE_IDENTICAL3', rows)

"""Verify retained archive members, actual callback nonlocal endpoints and unchanged complete-frame replay."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-callback-profile'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
parent_path = root / 'window-movie-input/build.json'
parent = json.loads(parent_path.read_text())
assert sha(parent_path) == build['parentBuildSha256']
header = (output / 'stock_movie_timing.h').read_text()
for before, after in reversed(build['headerPatches']):
    assert header.count(after) == 1
    header = header.replace(after, before, 1)
assert header == (root / 'window-movie-input/stock_movie_timing.h').read_text()
prepared_path = root / 'callback-profile-component/verification.json'
assert sha(prepared_path) == build['preparedComponentSha256']
prepared = json.loads(prepared_path.read_text())
archive = output / 'libnwiiruntime.a'
assert sha(archive) == build['archiveSha256']
old_archive = next(Path(arg) for arg in parent['linkCommand'] if Path(arg).name == 'libnwiiruntime.a')
for member, digest in build['members'].items():
    data = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    assert hashlib.sha256(data).hexdigest() == digest
    if member != 'ios.cpp.o':
        assert data == subprocess.check_output(['/usr/bin/ar', '-p', str(old_archive), member])
temporary = Path(tempfile.mkdtemp(prefix='openshsm-callback-contract-', dir='/private/tmp'))
probe = public / 'stock_callback_runtime_probe.cpp'
obj = temporary / 'callback.cpp.o'
flags = build['changes']['37']['arguments']
compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *flags,
    '-c', str(probe), '-o', str(obj)], capture_output=True, text=True, timeout=60)
assert compiled.returncode == 0, compiled.stderr[-2500:]
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
env['NWII_MOVIE_TIMING'] = str(temporary / 'profile-enabled')
callback_records = []
for label, configuration in [('baseline', parent), ('profile', build)]:
    command = list(configuration['linkCommand'])
    main = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
    command[command.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
    command.insert(1, str(obj))
    exe = temporary / label
    command[command.index('-o') + 1] = str(exe)
    linked = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
    assert linked.returncode == 0, linked.stderr[-2500:]
    endpoint = output / f'callback-{label}.bin'
    result = subprocess.run([str(exe), str(endpoint)], env=env, capture_output=True, text=True, timeout=30)
    (output / f'callback-{label}.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and 'ACTUAL_CALLBACK_QUEUE_NONLOCAL_ENDPOINT_PASS4' in result.stdout, result.stdout + result.stderr
    callback_records.append({'variant': label, 'executablePath': str(exe), 'executableSha256': sha(exe), 'endpointSha256': sha(endpoint)})
assert (output / 'callback-baseline.bin').read_bytes() == (output / 'callback-profile.bin').read_bytes()
command = list(build['linkCommand'])
main = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
command[command.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
fixture = root / 'window-decoder-o3/frame-probe.cpp.o'
proof = json.loads((root / 'window-decoder-o3/verification.json').read_text())
assert sha(fixture) == proof['fixtureObjectSha256']
command.insert(1, str(fixture))
frame_exe = temporary / 'frame'
command[command.index('-o') + 1] = str(frame_exe)
linked = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert linked.returncode == 0, linked.stderr[-2500:]
snapshot = root / 'headless-sc-pc-decoder-snapshot-retry-decoder-entry.bin'
packet = root / 'headless-thp-snapshot/hm1ply-frame15-replay/hm1ply-frame15.packet'
assert sha(snapshot) == proof['snapshotSha256'] and sha(packet) == proof['packetSha256']
reference = root / 'window-decoder-o3/baseline-0.yuv'
rows = []
for iteration in range(3):
    raw = output / f'probe-{iteration}.yuv'
    timing = output / f'probe-{iteration}-timing.jsonl'
    assert not timing.exists()
    selected_env = dict(env)
    selected_env['NWII_MOVIE_TIMING'] = str(timing)
    result = subprocess.run([str(frame_exe), str(snapshot), str(raw), str(packet)], env=selected_env,
        capture_output=True, text=True, timeout=30)
    log = output / f'probe-{iteration}.log'
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-2500:]
    assert raw.read_bytes() == reference.read_bytes()
    assert Path(str(raw) + '.state').read_bytes() == Path(str(reference) + '.state').read_bytes()
    events = [json.loads(line) for line in timing.read_text().splitlines()]
    assert [row['site'] for row in events] == [0x80209D80, 0x8020A044]
    first, last = events[0]['callbackProfile'], events[1]['callbackProfile']
    assert all(a <= b for a, b in zip(first, last)) and last[0] > first[0] and last[8] == 0
    rows.append({'outputSha256': sha(raw), 'stateSha256': sha(Path(str(raw) + '.state')),
        'timingSha256': sha(timing), 'logSha256': sha(log), 'profile': last,
        'wallUs': events[1]['hostUs'] - events[0]['hostUs']})
(output / 'component-verification.json').write_text(json.dumps({
    'result': 'CALLBACK_PROFILE_ACTUAL_NONLOCAL4_FRAME_STATE_IDENTICAL3', 'buildSha256': sha(build_path),
    'preparedComponentSha256': sha(prepared_path), 'verifierSha256': sha(Path(__file__)),
    'callbackProbeSha256': sha(probe), 'callbackProbeObjectSha256': sha(obj), 'callbackRecords': callback_records,
    'fixtureObjectSha256': sha(fixture), 'frameExecutablePath': str(frame_exe), 'frameExecutableSha256': sha(frame_exe),
    'rows': rows,
    'limits': ['Actual process_pending_callbacks retains EE0/inCallback queue gating and both queued callback nonlocal handoff paths.',
        'Exact baseline/profile selected native endpoints/three bounded memory regions, not full original Wii IRQ/controller proof.',
        'Observer enabled, same HM1PLY15 complete YUV/selected PPC state/inst_count identical.',
        'All other archive members and guest instructions retained; live sampled CPU fractions/GUI/audio/profile still pending.']}, indent=2) + '\n')
print('CALLBACK_PROFILE_ACTUAL_NONLOCAL4_FRAME_STATE_IDENTICAL3', rows)

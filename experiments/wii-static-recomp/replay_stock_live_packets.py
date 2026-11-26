"""Replay exact live input bytes in the existing uninterrupted decoder fixture; retain context caveats."""
from pathlib import Path
import hashlib
import json
import os
import re
import statistics
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'live-packet-replay'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
audit_path = root / 'window-movie-input/live-input-audit.json'
audit = json.loads(audit_path.read_text())
assert audit['result'] == 'LIVE_CALLER_PACKETS_EXACT_OWNED_CONTENT_INTERVALS_AUDITED'
assert sha(Path('experiments/wii-static-recomp/audit_stock_movie_input.py')) == audit['auditorSha256']
component_path = root / 'window-movie-input/component-verification.json'
component = json.loads(component_path.read_text())
assert sha(component_path) == audit['componentSha256']
build_path = root / 'window-movie-input/build.json'
build = json.loads(build_path.read_text())
assert sha(build_path) == audit['buildSha256'] == component['buildSha256']
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
exe = Path(component['executablePath'])
assert sha(exe) == component['executableSha256']
snapshot = root / 'headless-sc-pc-decoder-snapshot-retry-decoder-entry.bin'
snapshot_proof_path = root / 'movie-packet-metadata/verification.json'
snapshot_proof = json.loads(snapshot_proof_path.read_text())
assert sha(snapshot_proof_path) == component['priorMetadataEvidenceSha256']
assert sha(snapshot) == snapshot_proof['snapshotSha256']
data_path = root / 'headless-sc-pc-movie-input-movie-timing.jsonl.inputs.bin'
assert sha(data_path) == audit['dataSha256']
data = data_path.read_bytes()
for movie in audit['movieSources']:
    assert sha(Path(movie['path'])) == movie['sha256']
cases = []
for movie in ('PUBDEV', 'INTRO', 'LOOP'):
    candidates = [row for row in audit['records'] if row['end'] and len(row['moduloPositionMatches']) == 1
        and row['moduloPositionMatches'][0]['movie'] == movie and row['capture']['bytes'] <= 65536]
    assert candidates
    median = statistics.median(row['wallUs'] for row in candidates)
    selected = min(candidates, key=lambda row: abs(row['wallUs'] - median))
    capture = selected['capture']
    packet = data[capture['offset']:capture['offset'] + capture['bytes']]
    assert hashlib.sha256(packet).hexdigest() == capture['packetSha256']
    packet_path = output / f'{movie.lower()}-capture-{capture["index"]}.packet'
    assert not packet_path.exists()
    packet_path.write_bytes(packet)
    cases.append({'movie': movie, 'selectedLiveRecord': selected, 'packetPath': str(packet_path), 'replays': []})
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
for iteration in range(3):
    order = cases if iteration % 2 == 0 else list(reversed(cases))
    for case in order:
        raw = output / f'{case["movie"].lower()}-{iteration}.yuv'
        assert not raw.exists()
        result = subprocess.run([str(exe), str(snapshot), str(raw), case['packetPath']],
            env=env, capture_output=True, text=True, timeout=30)
        log = output / f'{case["movie"].lower()}-{iteration}.log'
        log.write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-2500:]
        match = re.search(r'COMPLETE_FRAME_REPLAY_RETURN0 ns=(\d+)', result.stdout)
        assert match and raw.stat().st_size == 460800
        state = Path(str(raw) + '.state')
        if iteration:
            assert raw.read_bytes() == (output / f'{case["movie"].lower()}-0.yuv').read_bytes()
            assert state.read_bytes() == (output / f'{case["movie"].lower()}-0.yuv.state').read_bytes()
        case['replays'].append({'iteration': iteration, 'terminalReturncode': result.returncode,
            'decoderNs': int(match[1]), 'outputSha256': sha(raw), 'stateSha256': sha(state), 'logSha256': sha(log)})
summaries = []
for case in cases:
    record = case['selectedLiveRecord']
    case['nativeMedianUs'] = statistics.median(row['decoderNs'] / 1000 for row in case['replays'])
    summaries.append({'movie': case['movie'], 'frame': record['moduloPositionMatches'][0]['frame'],
        'captureIndex': record['capture']['index'], 'packetBytes': record['capture']['bytes'],
        'liveWallUs': record['wallUs'], 'liveHostCpuUs': record['hostCpuUs'],
        'nativeMedianUs': case['nativeMedianUs']})
(output / 'verification.json').write_text(json.dumps({
    'result': 'EXACT_LIVE_PACKET_UNINTERRUPTED_REPLAYS_IDENTICAL3_EACH',
    'auditedLiveInputSha256': sha(audit_path), 'buildSha256': sha(build_path),
    'componentSha256': sha(component_path), 'snapshotSha256': sha(snapshot),
    'executablePath': str(exe), 'executableSha256': sha(exe), 'verifierSha256': sha(Path(__file__)),
    'cases': cases, 'summary': summaries,
    'limits': ['Exact live input packets, same current decoder objects; three repeat outputs/selected final states identical per packet.',
        'Replay uses earlier PUBDEV snapshot, relocated input and MSR.EE=0, not each live entry register/device/memory context.',
        'Live host-thread interval includes other guest threads/IRQ/runtime; time difference does not isolate scheduler-only cost.',
        'Repeat determinism not independent live YUV/physical Wii oracle or controlled game speedup.',
        'No GUI/audio/profile/save/controller/full movie/release acceptance; private packets and YUV not published.']}, indent=2) + '\n')
print('EXACT_LIVE_PACKET_UNINTERRUPTED_REPLAYS_IDENTICAL3_EACH')
print(json.dumps(summaries, indent=2))

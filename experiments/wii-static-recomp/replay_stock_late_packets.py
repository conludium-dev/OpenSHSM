"""Replay exact late owned packets with current objects, controlled clock/EE and temporary large evidence."""
from pathlib import Path
import hashlib
import json
import os
import re
import statistics
import struct
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'late-packet-replay'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
audit_path = root / 'window-movie-late/live-input-audit.json'
audit = json.loads(audit_path.read_text())
assert audit['result'] == 'DELAYED_LIVE_OWNED_MOVIE_PACKETS_AUDITED'
assert sha(Path('experiments/wii-static-recomp/audit_stock_movie_late.py')) == audit['auditorSha256']
build_path = root / 'window-movie-late/build.json'
build = json.loads(build_path.read_text())
component_path = root / 'window-movie-late/component-verification.json'
component = json.loads(component_path.read_text())
assert audit['buildSha256'] == sha(build_path) == component['buildSha256']
assert audit['componentSha256'] == sha(component_path)
assert component['result'] == 'MOVIE_LATE_GATE_PACKET_FRAME_STATE_IDENTICAL3'
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
for unit, change in build['changes'].items():
    assert (root / 'window-movie-late' / f'output_{unit}.cpp').read_bytes() == Path(change['originalPath']).read_bytes()
    assert sha(root / 'window-movie-late' / f'output_{unit}.cpp.o') == change['objectSha256']
for movie in audit['movieSources']:
    assert sha(Path(movie['path'])) == movie['sha256']
data_path = root / 'headless-sc-pc-movie-late-retry-movie-timing.jsonl.inputs.bin'
assert sha(data_path) == audit['dataSha256']
data = data_path.read_bytes()
snapshot = root / 'headless-sc-pc-decoder-snapshot-retry-decoder-entry.bin'
snapshot_proof = root / 'movie-packet-metadata/verification.json'
assert sha(snapshot_proof) == component['priorMetadataEvidenceSha256']
assert sha(snapshot) == json.loads(snapshot_proof.read_text())['snapshotSha256']
original_fixture = Path(component['executablePath']).parent / 'frame.cpp'
assert sha(original_fixture) == component['fixtureSourceSha256']
before = '        ctx.msr = (ctx.msr | 0x2000u) & ~0x8000u;'
after = '''        ctx.tb_freq = 60750000;
        ctx.msr = (ctx.msr | 0x2000u) & ~0x8000u;
        if (std::getenv("SHSM_REPLAY_EE1")) { ctx.msr |= 0x8000u; }'''
source_text = original_fixture.read_text()
assert source_text.count(before) == 1
temporary = Path(tempfile.mkdtemp(prefix='openshsm-late-replay-', dir='/private/tmp'))
source, obj, exe = temporary / 'frame.cpp', temporary / 'frame.cpp.o', temporary / 'frame'
source.write_text(source_text.replace(before, after, 1))
flags = build['changes']['37']['arguments']
compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *flags,
    '-I', str(root / 'window-movie-late'), '-c', str(source), '-o', str(obj)],
    capture_output=True, text=True, timeout=60)
assert compiled.returncode == 0, compiled.stderr[-2500:]
command = list(build['linkCommand'])
main = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
command[command.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
command.insert(1, str(obj))
command[command.index('-o') + 1] = str(exe)
linked = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert linked.returncode == 0, linked.stderr[-2500:]
cases = []
for movie in ('LOOP', 'MONTAGE'):
    candidates = [record for record in audit['records'] if record['end'] and
        len(record['moduloPositionMatches']) == 1 and record['moduloPositionMatches'][0]['movie'] == movie
        and record['capture']['bytes'] <= 65536]
    assert candidates
    if movie == 'LOOP':
        record = next(record for record in candidates if record['moduloPositionMatches'][0]['frame'] == 299)
    else:
        median = statistics.median(record['wallUs'] for record in candidates)
        record = min(candidates, key=lambda record: abs(record['wallUs'] - median))
    capture = record['capture']
    packet = data[capture['offset']:capture['offset'] + capture['bytes']]
    assert hashlib.sha256(packet).hexdigest() == capture['packetSha256']
    packet_path = temporary / f'{movie.lower()}.packet'
    packet_path.write_bytes(packet)
    cases.append({'movie': movie, 'selectedLiveRecord': record, 'packetPath': str(packet_path)})
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
msr_offset = 720
rows = []
references = {}
for iteration in range(3):
    for case in (cases if iteration % 2 == 0 else list(reversed(cases))):
        for mode in ('instruction-ee0', 'wall-ee0', 'wall-ee1'):
            raw = temporary / f'{case["movie"].lower()}-{mode}-{iteration}.yuv'
            selected_env = dict(env)
            if mode.startswith('wall'):
                selected_env['NWII_WALLTB'] = '1'
            if mode.endswith('ee1'):
                selected_env['SHSM_REPLAY_EE1'] = '1'
            run = subprocess.run([str(exe), str(snapshot), str(raw), case['packetPath']], env=selected_env,
                capture_output=True, text=True, timeout=30)
            log = raw.with_suffix('.log')
            log.write_text(run.stdout + run.stderr)
            assert run.returncode == 0, run.stderr[-2500:]
            match = re.search(r'COMPLETE_FRAME_REPLAY_RETURN0 ns=(\d+)', run.stdout)
            assert match and raw.stat().st_size == 460800
            state_path = Path(str(raw) + '.state')
            state = bytearray(state_path.read_bytes())
            msr = struct.unpack_from('<I', state, msr_offset)[0]
            assert bool(msr & 0x8000) == mode.endswith('ee1')
            struct.pack_into('<I', state, msr_offset, msr & ~0x8000)
            endpoint = (raw.read_bytes(), bytes(state))
            if case['movie'] in references:
                assert endpoint == references[case['movie']]
            else:
                references[case['movie']] = endpoint
            rows.append({'movie': case['movie'], 'mode': mode, 'iteration': iteration,
                'decoderNs': int(match[1]), 'outputPath': str(raw), 'outputSha256': sha(raw),
                'rawStateSha256': sha(state_path), 'normalizedStateSha256': hashlib.sha256(state).hexdigest(),
                'logPath': str(log), 'logSha256': sha(log)})
summary = []
for case in cases:
    record = case['selectedLiveRecord']
    summary.append({'movie': case['movie'], 'frame': record['moduloPositionMatches'][0]['frame'],
        'captureIndex': record['capture']['index'], 'packetBytes': record['capture']['bytes'],
        'liveWallUs': record['wallUs'], 'liveCpuUs': record['hostCpuUs'],
        'nativeMedianUs': {mode: statistics.median(row['decoderNs'] / 1000 for row in rows
            if row['movie'] == case['movie'] and row['mode'] == mode)
            for mode in ('instruction-ee0', 'wall-ee0', 'wall-ee1')}})
report = {'result': 'LATE_EXACT_PACKETS_CURRENT_OBJECTS_CLOCK_EE_ENDPOINTS_EQUAL18',
    'auditSha256': sha(audit_path), 'buildSha256': sha(build_path), 'componentSha256': sha(component_path),
    'snapshotSha256': sha(snapshot), 'dataSha256': sha(data_path), 'originalFixtureSha256': sha(original_fixture),
    'sourceSha256': sha(source), 'objectSha256': sha(obj), 'executablePath': str(exe), 'executableSha256': sha(exe),
    'verifierSha256': sha(Path(__file__)), 'fixturePatch': [before, after], 'linkCommand': command,
    'timebaseFrequency': 60750000, 'msrOffset': msr_offset, 'cases': cases, 'rows': rows, 'summary': summary,
    'limits': ['Exact late live input bytes/current decoder-runtime objects; repeat YUV and selected PPC state equal after only EE normalization.',
        'Fixture uses earlier PUBDEV entry snapshot/relocated input, not each late live register/memory/device context.',
        'Wall60.75MHz/EEbit controls do not create live GUI/device IRQ producers or pending callbacks.',
        'Live interval includes other guest/IRQ/runtime; differences not scheduler-exclusive cost or controlled game speedup.',
        'No independent live YUV/physical Wii oracle, visual/audio/profile/save/controller/full-game acceptance or promotion.',
        'Large sources/objects/executable/packets/YUV stored in explicit temporary cache; small report on Data.']}
(output / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
print(report['result'])
print(json.dumps(summary, indent=2))

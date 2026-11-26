"""Replay latest owned live packets on the exact current archive/guest objects."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import statistics
import struct
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2] / 'work/private-game/static-recomp/stock-baseline'
parser = argparse.ArgumentParser()
parser.add_argument('--bp-order-menu', action='store_true')
parser.add_argument('--artifacts', type=Path)
args = parser.parse_args()
assert args.bp_order_menu == (args.artifacts is not None)
candidate = 'window-bp-order' if args.bp_order_menu else 'window-post-present'
tag = 'bp-order-menu' if args.bp_order_menu else 'post-present-live'
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
build_path = root / candidate / 'build.json'
build = json.loads(build_path.read_text())
component_path = build_path.parent / 'component-verification.json'
component = json.loads(component_path.read_text())
assert component['buildSha256'] == sha(build_path)
assert component['result'] == ('BP_ORDER_NATIVE_SHADER_GPU_PIPELINE_RETAINED_PARENT_VERIFIED'
    if args.bp_order_menu else 'POST_PRESENT_GPU22_MAIN_DELTA_RETAINED_PARENT_COMPONENTS_VERIFIED')
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(path) == digest
assert sha(build['executablePath']) == build['executableSha256']
assert sha(build['archivePath']) == build['archiveSha256']
artifacts = args.artifacts.resolve() if args.bp_order_menu else None
audit_path = artifacts / 'profile-input-audit.json' if args.bp_order_menu else build_path.parent / 'live-input-audit.json'
audit = json.loads(audit_path.read_text())
assert audit['buildSha256'] == sha(build_path) and audit['componentSha256'] == sha(component_path)
if not args.bp_order_menu:
    artifacts = Path(audit['artifactDirectory'])
assert artifacts.parent == Path('/private/tmp')
run_path = artifacts / f'headless-sc-pc-headless-windowed-{tag}-result.json'
run = json.loads(run_path.read_text())
assert sha(run_path) == audit['runSha256']
assert run['terminalReturncode'] == 0 and run['deadlineReached']
assert run['executableSha256'] == build['executableSha256']
timing = artifacts / f'headless-sc-pc-{tag}-movie-timing.jsonl'
data_path = Path(str(timing) + '.inputs.bin')
metadata_path = Path(str(timing) + '.inputs.jsonl')
assert sha(timing) == audit['timingSha256']
assert sha(data_path) == audit['dataSha256'] and sha(metadata_path) == audit['metadataSha256']
data = data_path.read_bytes()
for movie in audit['movieSources']:
    assert sha(movie['path']) == movie['sha256']
prior_path = root / 'late-packet-replay/verification.json'
prior = json.loads(prior_path.read_text())
assert prior['result'] == 'LATE_EXACT_PACKETS_CURRENT_OBJECTS_CLOCK_EE_ENDPOINTS_EQUAL18'
fixture = Path(prior['linkCommand'][1])
assert sha(fixture) == prior['objectSha256']
snapshot = root / 'headless-sc-pc-decoder-snapshot-retry-decoder-entry.bin'
assert sha(snapshot) == prior['snapshotSha256']
cache = Path(tempfile.mkdtemp(prefix='openshsm-bp-loop-replay-' if args.bp_order_menu
    else 'openshsm-post-packet-replay-', dir='/private/tmp'))
command = list(build['linkCommand'])
main = next(arg for arg in command if Path(arg).name == 'main.cpp.o') if args.bp_order_menu else build['changes']['main.cpp']['objectPath']
entry = root / 'headless-tev-banks/contract-entry.cpp.o'
command[command.index(main)] = str(entry)
command.insert(1, str(fixture))
exe = cache / 'frame'
command[command.index('-o') + 1] = str(exe)
linked = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert linked.returncode == 0, linked.stderr[-3000:]
candidates = [row for row in audit['records'] if row['end'] and row['capture']['bytes'] <= 65536
    and len(row['moduloPositionMatches']) == 1 and row['moduloPositionMatches'][0]['movie'] == ('LOOP' if args.bp_order_menu else 'MONTAGE')]
assert candidates and all(row['hostCpuUs'] >= 0 for row in candidates)
median = statistics.median(row['hostCpuUs'] for row in candidates)
selected = [('fast', min(candidates, key=lambda row: row['hostCpuUs'])),
    ('median', min(candidates, key=lambda row: abs(row['hostCpuUs'] - median))),
    ('slow', max(candidates, key=lambda row: row['hostCpuUs']))]
assert len({row['capture']['index'] for _, row in selected}) == 3
cases = []
for label, record in selected:
    capture = record['capture']
    packet = data[capture['offset']:capture['offset'] + capture['bytes']]
    assert hashlib.sha256(packet).hexdigest() == capture['packetSha256']
    path = cache / f'{label}.packet'
    path.write_bytes(packet)
    cases.append({'label': label, 'selectedLiveRecord': record, 'packetPath': str(path)})
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
rows = []
reference = {}
for iteration in range(3):
    for case in (cases if iteration % 2 == 0 else list(reversed(cases))):
        for mode in ('instruction-ee0', 'wall-ee0', 'wall-ee1'):
            raw = cache / f'{case["label"]}-{mode}-{iteration}.yuv'
            selected_env = dict(env)
            if mode.startswith('wall'):
                selected_env['NWII_WALLTB'] = '1'
            if mode.endswith('ee1'):
                selected_env['SHSM_REPLAY_EE1'] = '1'
            run = subprocess.run([str(exe), str(snapshot), str(raw), case['packetPath']],
                env=selected_env, capture_output=True, text=True, timeout=30)
            log = raw.with_suffix('.log')
            log.write_text(run.stdout + run.stderr)
            match = re.search(r'COMPLETE_FRAME_REPLAY_RETURN0 ns=(\d+)', run.stdout)
            assert run.returncode == 0 and match and raw.stat().st_size == 460800, run.stdout + run.stderr
            state_path = Path(str(raw) + '.state')
            state = bytearray(state_path.read_bytes())
            msr = struct.unpack_from('<I', state, prior['msrOffset'])[0]
            assert bool(msr & 0x8000) == mode.endswith('ee1')
            struct.pack_into('<I', state, prior['msrOffset'], msr & ~0x8000)
            endpoint = (raw.read_bytes(), bytes(state))
            if case['label'] in reference:
                assert endpoint == reference[case['label']]
            else:
                reference[case['label']] = endpoint
            rows.append({'label': case['label'], 'mode': mode, 'iteration': iteration,
                'decoderNs': int(match[1]), 'outputPath': str(raw), 'outputSha256': sha(raw),
                'rawStateSha256': sha(state_path), 'normalizedStateSha256': hashlib.sha256(state).hexdigest(),
                'logPath': str(log), 'logSha256': sha(log)})
summary = []
for case in cases:
    live = case['selectedLiveRecord']
    summary.append({'label': case['label'], 'frame': live['moduloPositionMatches'][0]['frame'],
        'packetSha256': live['capture']['packetSha256'], 'liveWallUs': live['wallUs'], 'liveHostCpuUs': live['hostCpuUs'],
        'isolatedMedianUs': {mode: statistics.median(row['decoderNs'] / 1000 for row in rows
            if row['label'] == case['label'] and row['mode'] == mode)
            for mode in ('instruction-ee0', 'wall-ee0', 'wall-ee1')}})
report = {'result': ('BP_ORDER_LOOP_SAME_PACKETS_ISOLATED_CLOCK_EE_ENDPOINTS_EQUAL27' if args.bp_order_menu
    else 'POST_PRESENT_SAME_PACKETS_ISOLATED_CLOCK_EE_ENDPOINTS_EQUAL27'),
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), build_path, component_path,
        audit_path, run_path, timing, data_path, metadata_path, prior_path, fixture, snapshot, entry]},
    'linkCommand': command, 'executablePath': str(exe), 'executableSha256': sha(exe),
    'cases': cases, 'rows': rows, 'summary': summary,
    'liveMedianWallUs': statistics.median(row['wallUs'] for row in candidates),
    'liveMedianHostCpuUs': statistics.median(row['hostCpuUs'] for row in candidates),
    'limits': ['Exact current owned packet bytes/archive/guest objects, complete YUV and selected PPC state equal in27 isolated executions.',
        'Earlier PUBDEV entry snapshot with relocated packet, NOT captured live register/memory/device context for these frames.',
        'Live host-thread CPU includes other guest/IRQ/runtime on that thread; not decoder-exclusive cost.',
        'Clock/EE controls do not reproduce asynchronous GUI/IRQ producers or prove which live path consumes extra CPU.',
        'No independent original Wii/live stable YUV oracle, visual acceptance, optimization or default promotion.']}
path = cache / 'verification.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
print(json.dumps(summary, indent=2))

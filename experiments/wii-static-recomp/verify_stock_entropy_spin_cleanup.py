"""Alternate exact same-packet baseline/candidate replay; compare full outputs and time."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import statistics
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--build', type=Path, required=True)
parser.add_argument('--replay-proof', type=Path, required=True)
args = parser.parse_args()
build_path, proof_path = args.build.resolve(), args.replay_proof.resolve()
assert build_path.parent.parent == Path('/private/tmp') and build_path.parent.name.startswith('openshsm-entropy-spin-')
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
build = json.loads(build_path.read_text())
proof = json.loads(proof_path.read_text())
assert build['result'] == 'ENTROPY_SPIN_CONSOLE_ONLY_BUILT_UNVERIFIED'
assert proof['result'] == 'BP_ORDER_LOOP_SAME_PACKETS_ISOLATED_CLOCK_EE_ENDPOINTS_EQUAL27'
assert all(sha(path) == value for path, value in {**build['dependencies'], **build['retainedInputs']}.items())
assert all(sha(path) == value for path, value in proof['dependencies'].items())
assert sha(build['archivePath']) == build['archiveSha256']
assert sha(build['objectPath']) == build['objectSha256']
assert sha(build['sourcePath']) == build['sourceSha256']
original = Path(build['originalSourcePath']).read_text()
for line in build['removedConsoleLines']:
    assert original.count(line) == 1
    original = original.replace(line, '', 1)
assert original == Path(build['sourcePath']).read_text()
project = Path(__file__).resolve().parents[2]
root = project / 'work/private-game/static-recomp/stock-baseline'
cache = Path(tempfile.mkdtemp(prefix='openshsm-entropy-spin-tests-', dir='/private/tmp'))
fixture = proof['linkCommand'][1]
link = list(build['linkCommand'])
main = next(arg for arg in link if Path(arg).name == 'main.cpp.o')
link[link.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
link.insert(1, fixture)
candidate = cache / 'frame'
link[link.index('-o') + 1] = str(candidate)
linked = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert linked.returncode == 0, linked.stderr[-3000:]
baseline = Path(proof['executablePath'])
assert sha(baseline) == proof['executableSha256']
snapshot = root / 'headless-sc-pc-decoder-snapshot-retry-decoder-entry.bin'
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
env.update(NWII_WALLTB='1', SHSM_REPLAY_EE1='1')
rows = []
for iteration in range(6):
    for case in (proof['cases'] if iteration % 2 == 0 else list(reversed(proof['cases']))):
        reference = next(row for row in proof['rows'] if row['label'] == case['label']
            and row['mode'] == 'wall-ee1' and row['iteration'] == 0)
        assert sha(case['packetPath']) == case['selectedLiveRecord']['capture']['packetSha256']
        for mode in (('baseline', 'candidate') if iteration % 2 == 0 else ('candidate', 'baseline')):
            raw = cache / f'{case["label"]}-{mode}-{iteration}.yuv'
            exe = baseline if mode == 'baseline' else candidate
            run = subprocess.run([str(exe), str(snapshot), str(raw), case['packetPath']],
                env=env, capture_output=True, text=True, timeout=30)
            match = re.search(r'COMPLETE_FRAME_REPLAY_RETURN0 ns=(\d+)', run.stdout)
            assert run.returncode == 0 and match, run.stdout + run.stderr
            assert sha(raw) == reference['outputSha256']
            assert sha(str(raw) + '.state') == reference['rawStateSha256']
            log = raw.with_suffix('.log')
            log.write_text(run.stdout + run.stderr)
            rows.append({'label': case['label'], 'mode': mode, 'iteration': iteration,
                'decoderNs': int(match[1]), 'outputPath': str(raw), 'outputSha256': sha(raw),
                'stateSha256': sha(str(raw) + '.state'), 'logPath': str(log), 'logSha256': sha(log)})
summary = []
for case in proof['cases']:
    modes = {mode: [row['decoderNs'] / 1e6 for row in rows if row['label'] == case['label'] and row['mode'] == mode]
        for mode in ('baseline', 'candidate')}
    summary.append({'label': case['label'], 'baselineMs': modes['baseline'], 'candidateMs': modes['candidate'],
        'baselineMedianMs': statistics.median(modes['baseline']), 'candidateMedianMs': statistics.median(modes['candidate'])})
report = {'result': 'ENTROPY_SPIN_SAME_PACKETS_FULL_YUV_SELECTED_PPC_EQUAL36',
    'buildSha256': sha(build_path), 'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(),
        proof_path, baseline, snapshot, Path(fixture)]}, 'linkCommand': link,
    'executablePath': str(candidate), 'executableSha256': sha(candidate), 'rows': rows, 'summary': summary,
    'limits': ['Alternating six fresh-process repetitions per case/mode; same packet and existing isolated snapshot.',
        'Only console diagnostic conditions removed, all output/state checks exact; not original Wii timing or live IRQ-context proof.',
        'Host core/scheduling/thermal state uncontrolled; distributions and medians, not guaranteed live FPS gain.',
        'CPU/SC/callback/DEC regression and actual game visual/audio/performance acceptance pending; not registered/default.']}
path = cache / 'verification.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
print(json.dumps(summary, indent=2))

"""Compare exact same owned packet IDs across parent/candidate, retaining context caveats."""
from pathlib import Path
import argparse
import hashlib
import json
import statistics

parser = argparse.ArgumentParser()
parser.add_argument('--artifacts', type=Path, required=True)
args = parser.parse_args()
artifacts = args.artifacts.resolve()
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
root = Path(__file__).resolve().parents[2] / 'work/private-game/static-recomp/stock-baseline'
parent_path = root / 'window-post-present/live-input-audit.json'
candidate_path = root / 'window-context-stage/live-input-audit.json'
parent = json.loads(parent_path.read_text())
candidate = json.loads(candidate_path.read_text())
assert Path(candidate['artifactDirectory']) == artifacts
def check(report, tag, directory):
    run_path = Path(report['artifactDirectory']) / f'headless-sc-pc-headless-windowed-{tag}-result.json'
    run = json.loads(run_path.read_text())
    assert sha(run_path) == report['runSha256']
    assert run['terminalReturncode'] == 0 and run['deadlineReached']
    build_path = root / directory / 'build.json'
    assert report['buildSha256'] == sha(build_path)
    build = json.loads(build_path.read_text())
    assert run['executableSha256'] == build['executableSha256'] == sha(build['executablePath'])
check(parent, 'post-present-live', 'window-post-present')
check(candidate, 'context-stage-live', 'window-context-stage')
def key(row):
    if not row['end'] or len(row['moduloPositionMatches']) != 1:
        return None
    frame = row['moduloPositionMatches'][0]
    return frame['movie'], frame['frame'], row['capture']['packetSha256']
old = {key(row): row for row in parent['records'] if key(row)}
pairs = []
for row in candidate['records']:
    match = key(row)
    if match not in old:
        continue
    before = old[match]
    pairs.append({'movie': match[0], 'frame': match[1], 'packetSha256': match[2],
        'beforeWallUs': before['wallUs'], 'afterWallUs': row['wallUs'],
        'beforeHostCpuUs': before['hostCpuUs'], 'afterHostCpuUs': row['hostCpuUs']})
summary = []
for movie in sorted({row['movie'] for row in pairs}):
    group = [row for row in pairs if row['movie'] == movie]
    summary.append({'movie': movie, 'pairs': len(group),
        'beforeMedianWallUs': statistics.median(row['beforeWallUs'] for row in group),
        'afterMedianWallUs': statistics.median(row['afterWallUs'] for row in group),
        'beforeMedianHostCpuUs': statistics.median(row['beforeHostCpuUs'] for row in group),
        'afterMedianHostCpuUs': statistics.median(row['afterHostCpuUs'] for row in group)})
report = {'result': 'CONTEXT_STAGE_PARENT_EXACT_PACKET_COMPARISON_AUDITED',
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), parent_path, candidate_path]},
    'pairs': pairs, 'summary': summary,
    'limits': ['Exact same owned movie/frame/packet bytes, not identical guest/IRQ/device/CPU core history.',
        'Separate sessions/diagnostic IO; matching samples do not prove a controlled percentage gain.',
        'No matching packet pairs is recorded explicitly, never replaced with different-frame comparisons.']}
path = artifacts / 'parent-packet-comparison.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
print(json.dumps(summary, indent=2))

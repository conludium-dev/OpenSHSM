"""Compare only shared exact packet/frame identities across separate live runs, not full-context controlled speedup."""
from pathlib import Path
import hashlib
import json
import statistics

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
old_path = root / 'window-movie-input/live-input-audit.json'
new_path = root / 'window-ios-o2/live-input-audit.json'
old = json.loads(old_path.read_text())
new = json.loads(new_path.read_text())
prior = json.loads((root / 'live-packet-replay/verification.json').read_text())
candidate = json.loads((root / 'window-ios-o2/live-audit.json').read_text())
assert sha(old_path) == prior['auditedLiveInputSha256']
assert sha(new_path) == candidate['packetAuditSha256']
assert old['result'] == new['result'] == 'LIVE_CALLER_PACKETS_EXACT_OWNED_CONTENT_INTERVALS_AUDITED'
assert old['movieSources'] == new['movieSources']
def identity(record):
    if not record['end'] or len(record['moduloPositionMatches']) != 1:
        return None
    match = record['moduloPositionMatches'][0]
    return (match['movie'], match['frame'], match['component'], record['capture']['packetSha256'])
lookup = {}
for record in old['records']:
    key = identity(record)
    if key:
        lookup.setdefault(key, []).append(record)
matched = []
for record in new['records']:
    key = identity(record)
    if key in lookup:
        for before in lookup[key]:
            matched.append({'movie': key[0], 'frame': key[1], 'component': key[2], 'packetSha256': key[3],
                'beforeCapture': before['capture']['index'], 'afterCapture': record['capture']['index'],
                'beforeWallUs': before['wallUs'], 'afterWallUs': record['wallUs'],
                'beforeHostCpuUs': before['hostCpuUs'], 'afterHostCpuUs': record['hostCpuUs']})
assert matched
groups = {}
for row in matched:
    groups.setdefault(row['movie'], []).append(row)
summary = {movie: {'matchedPairs': len(rows),
    'beforeMedianWallUs': statistics.median(row['beforeWallUs'] for row in rows),
    'afterMedianWallUs': statistics.median(row['afterWallUs'] for row in rows)} for movie, rows in groups.items()}
(root / 'window-ios-o2/matched-live-comparison.json').write_text(json.dumps({
    'result': 'SHARED_EXACT_PACKET_FRAME_LIVE_INTERVALS_COMPARED', 'beforeAuditSha256': sha(old_path),
    'afterAuditSha256': sha(new_path), 'candidateLiveAuditSha256': sha(root / 'window-ios-o2/live-audit.json'),
    'verifierSha256': sha(Path(__file__)), 'summary': summary, 'pairs': matched,
    'limits': ['Exact input content/movie/frame identity matched, not merely aggregate different-frame medians.',
        'Separate live runs with different host load/IRQ/device/guest entry context/capture conditions.',
        'Observed interval comparison, not exact causal percentage or full-game/render/audio speedup.',
        'Native callback/frame/SDK/SC equivalence separate; full Wii/visual/profile/controller acceptance incomplete.']}, indent=2) + '\n')
print('SHARED_EXACT_PACKET_FRAME_LIVE_INTERVALS_COMPARED')
print(json.dumps(summary, indent=2))

"""Bind current IOSO2 callback samples to exact late owned packets, not earlier O0 timing estimates."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import statistics

parser = argparse.ArgumentParser()
parser.add_argument('--artifacts', type=Path, required=True)
args = parser.parse_args()
artifacts = args.artifacts.resolve()
assert artifacts.parent == Path('/private/tmp') and re.fullmatch(r'openshsm-run-[A-Za-z0-9_-]+', artifacts.name)
run_path = artifacts / 'headless-sc-pc-headless-windowed-callback-o2-profile-result.json'
run = json.loads(run_path.read_text())
assert run['temporaryEvidence'] and Path(run['artifactDirectory']).resolve() == artifacts
assert run['movieCaptureAfterMs'] == 70000
base = Path('experiments/wii-static-recomp/audit_stock_movie_input.py')
script = base.read_text()
unit_block = '''for unit, change in build['changes'].items():
    assert (output / f'output_{unit}.cpp').read_bytes() == Path(change['originalPath']).read_bytes()
    assert sha(output / f'output_{unit}.cpp.o') == change['objectSha256']
'''
patches = [
    ("output = root / 'window-movie-input'", "output = root / 'window-callback-o2-profile'"),
    (unit_block, '''for unit, change in build['changes'].items():
    assert Path(change['sourcePath']).read_bytes() == Path(change['originalPath']).read_bytes()
    assert sha(Path(change['objectPath'])) == change['objectSha256']
'''),
    ("'ACTUAL_CONTEXT_PACKET_CAPTURE_FRAME_STATE_IDENTICAL3'", "'CURRENT_CALLBACK_O2_PROFILE_NONLOCAL4_SDK7_SC3_LATE18_EQUAL'"),
    ("cap['buildSha256'] == sha(build_path)", "cap['buildSha256'] == sha(root / 'window-movie-input/build.json')"),
    ("sha(output / 'OpenSHSMStockMovieInput')", "sha(Path(build['executablePath']))"),
    ('headless-sc-pc-headless-windowed-movie-input', 'headless-sc-pc-headless-windowed-callback-o2-profile'),
    ('headless-sc-pc-movie-input-movie-timing.jsonl', 'headless-sc-pc-callback-o2-profile-movie-timing.jsonl')]
for before, after in patches:
    assert before in script
    script = script.replace(before, after)
script = script.replace("root / 'headless-sc-pc-", "artifacts / 'headless-sc-pc-")
scope = {'__file__': __file__, 'artifacts': artifacts}
exec(compile(script, str(base), 'exec'), scope)
root, output, build = scope['root'], scope['output'], scope['build']
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
timing, records = scope['timing'], scope['records']
assert all(len(row['callbackProfile']) == 10 for row in timing)
assert all(all(a <= b for a, b in zip(first['callbackProfile'], last['callbackProfile']))
    for first, last in zip(timing, timing[1:]))
profiles = []
for record in records:
    if not record['end']:
        continue
    before, after = record['begin']['callbackProfile'], record['end']['callbackProfile']
    delta = [b - a for a, b in zip(before, after)]
    assert all(value >= 0 for value in delta)
    assert delta[2] <= delta[1] and delta[3] <= delta[0] and delta[4] <= delta[0]
    profiles.append({'captureIndex': record['capture']['index'], 'wallUs': record['wallUs'],
        'hostCpuUs': record['hostCpuUs'], 'matches': record['moduloPositionMatches'],
        'counts': dict(zip(build['counterOrder'], delta)), 'entryReturnDifference': delta[0] - delta[1],
        'sampleEntryReturnDifference': delta[5] - delta[6]})
assert profiles
def summarize(group):
    totals = {key: sum(row['counts'][key] for row in group) for key in build['counterOrder']}
    return {'completedIntervals': len(group), 'totals': totals,
        'medianCalls': statistics.median(row['counts']['calls'] for row in group),
        'medianContextRestores': statistics.median(row['counts']['successfulContextRestores'] for row in group),
        'medianWallUs': statistics.median(row['wallUs'] for row in group),
        'entriesWithoutOrdinaryReturn': sum(row['entryReturnDifference'] for row in group),
        'sampleEntriesWithoutOrdinaryReturn': sum(row['sampleEntryReturnDifference'] for row in group),
        'ordinarySampleMeanCpuNs': totals['sampleCpuNs'] / totals['sampledOrdinaryReturns'] if totals['sampledOrdinaryReturns'] else None}
summary = summarize(profiles)
summary['movies'] = {movie: summarize([row for row in profiles if len(row['matches']) == 1 and row['matches'][0]['movie'] == movie])
    for movie in sorted({row['matches'][0]['movie'] for row in profiles if len(row['matches']) == 1})}
log = artifacts / 'headless-sc-pc-headless-windowed-callback-o2-profile.log'
text = log.read_text()
host = re.findall(r'^\[HostPhases\] hostUs=(\d+) elapsedUs=(\d+)', text, re.M)
assert host and timing[0]['hostUs'] >= int(host[0][0]) - int(host[0][1]) + 69000000
(output / 'live-profile-audit.json').write_text(json.dumps({
    'result': 'CURRENT_IOS_O2_EXACT_LATE_PACKET_CALLBACK_PROFILE_AUDITED',
    'buildSha256': sha(output / 'build.json'), 'packetAuditSha256': sha(output / 'live-input-audit.json'),
    'baseAuditorSha256': sha(base), 'auditorSha256': sha(Path(__file__)), 'artifactDirectory': str(artifacts),
    'summary': summary, 'intervals': profiles,
    'lastCounters': dict(zip(build['counterOrder'], timing[-1]['callbackProfile'])),
    'limits': ['Current IOS O2/scheduler O2/exact helper/texture/late gate retained; profile not old O0 IOS timings.',
        'Same CPU-host thread includes other guest/IRQ execution; ordinary sampled mean includes clock/wrapper/counter overhead and periodic bias.',
        'Missing ordinary/sample returns are not exact IRQ counts or zero-duration completions; nonlocal/overlap possible.',
        'Successful HLE restores do not prove original hardware interrupt correctness.',
        'Counters perturb execution; no exclusive CPU fractions or controlled game FPS claim from sample extrapolation.',
        'No new capture/listening/profile/save/story/controller/hardware acceptance or promotion; temporary evidence may expire.']}, indent=2) + '\n')
print('CURRENT_IOS_O2_EXACT_LATE_PACKET_CALLBACK_PROFILE_AUDITED')
print(json.dumps(summary, indent=2))

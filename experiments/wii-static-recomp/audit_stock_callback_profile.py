"""Reuse exact owned-packet matching, then audit host callback counters over the matched intervals."""
from pathlib import Path
import hashlib
import json
import statistics

base = Path('experiments/wii-static-recomp/audit_stock_movie_input.py')
script = base.read_text()
patches = [
    ("output = root / 'window-movie-input'", "output = root / 'window-callback-profile'"),
    ("component['result'] == 'ACTUAL_CONTEXT_PACKET_CAPTURE_FRAME_STATE_IDENTICAL3'", "component['result'] == 'CALLBACK_PROFILE_ACTUAL_NONLOCAL4_FRAME_STATE_IDENTICAL3'"),
    ("cap['buildSha256'] == sha(build_path)", "cap['buildSha256'] == build['parentBuildSha256']"),
    ("sha(output / 'OpenSHSMStockMovieInput')", "sha(Path(build['executablePath']))"),
    ('headless-sc-pc-headless-windowed-movie-input-result.json', 'headless-sc-pc-headless-windowed-callback-profile-result.json'),
    ('headless-sc-pc-headless-windowed-movie-input.log', 'headless-sc-pc-headless-windowed-callback-profile.log'),
    ('headless-sc-pc-movie-input-movie-timing.jsonl', 'headless-sc-pc-callback-profile-movie-timing.jsonl')]
for before, after in patches:
    assert script.count(before) == 1
    script = script.replace(before, after, 1)
scope = {'__file__': __file__}
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
    before = record['begin']['callbackProfile']
    after = record['end']['callbackProfile']
    delta = [b - a for a, b in zip(before, after)]
    assert all(value >= 0 for value in delta)
    assert delta[2] <= delta[1] and delta[3] <= delta[0] and delta[4] <= delta[0]
    profiles.append({'captureIndex': record['capture']['index'], 'wallUs': record['wallUs'],
        'hostCpuUs': record['hostCpuUs'], 'matches': record['moduloPositionMatches'],
        'counts': dict(zip(build['counterOrder'], delta)),
        'entryReturnDifference': delta[0] - delta[1], 'sampleEntryReturnDifference': delta[5] - delta[6]})
assert profiles
totals = {key: sum(row['counts'][key] for row in profiles) for key in build['counterOrder']}
summary = {'completedCapturedIntervals': len(profiles), 'totals': totals,
    'medianCallsPerInterval': statistics.median(row['counts']['calls'] for row in profiles),
    'medianContextRestoresPerInterval': statistics.median(row['counts']['successfulContextRestores'] for row in profiles),
    'entriesWithoutOrdinaryReturn': sum(row['entryReturnDifference'] for row in profiles),
    'sampleEntriesWithoutOrdinaryReturn': sum(row['sampleEntryReturnDifference'] for row in profiles),
    'ordinarySampleMeanCpuNs': totals['sampleCpuNs'] / totals['sampledOrdinaryReturns'] if totals['sampledOrdinaryReturns'] else None}
packet_report_path = output / 'live-input-audit.json'
(output / 'live-profile-audit.json').write_text(json.dumps({
    'result': 'PACKET_IDENTIFIED_CALLBACK_COUNTS_SAMPLED_CPU_AUDITED',
    'buildSha256': sha(output / 'build.json'), 'packetAuditSha256': sha(packet_report_path),
    'baseAuditorSha256': sha(base), 'auditorSha256': sha(Path(__file__)),
    'summary': summary, 'intervals': profiles, 'lastCounters': dict(zip(build['counterOrder'], timing[-1]['callbackProfile'])),
    'limits': ['Same one CPU host thread, counters include other guest threads/IRQs within intervals.',
        'Ordinary sample mean includes clock/wrapper/counter overhead; periodic1/1024 selection may be biased.',
        'Entry-return differences include nonlocal exits and possible overlapping invocation boundaries; not exact IRQ count.',
        'Successful restores are actual existing HLE restore branch, not proof original hardware/correct scheduler.',
        'Observer runtime cost/context histories differ; no controlled FPS gain or exclusive CPU fraction.',
        'No visual/audio/profile/save/controller/full game/hardware acceptance or promotion.']}, indent=2) + '\n')
print('PACKET_IDENTIFIED_CALLBACK_COUNTS_SAMPLED_CPU_AUDITED')
print(json.dumps(summary, indent=2))

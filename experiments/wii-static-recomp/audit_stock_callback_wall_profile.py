"""Reuse exact late packet/counter audit with explicitly WALL-labelled diagnostic time."""
from pathlib import Path
import hashlib
import json

base = Path('experiments/wii-static-recomp/audit_stock_callback_o2_profile.py')
script = base.read_text()
patches = [
    ('window-callback-o2-profile', 'window-callback-wall-profile'),
    ('headless-sc-pc-headless-windowed-callback-o2-profile', 'headless-sc-pc-headless-windowed-callback-wall-profile'),
    ('headless-sc-pc-callback-o2-profile-movie-timing.jsonl', 'headless-sc-pc-callback-wall-profile-movie-timing.jsonl'),
    ('CURRENT_CALLBACK_O2_PROFILE_NONLOCAL4_SDK7_SC3_LATE18_EQUAL', 'CURRENT_CALLBACK_WALL_PROFILE_NONLOCAL4_SDK7_SC3_LATE18_EQUAL'),
    ('CURRENT_IOS_O2_EXACT_LATE_PACKET_CALLBACK_PROFILE_AUDITED', 'CURRENT_IOS_WALL_CLOCK_EXACT_LATE_PACKET_CALLBACK_PROFILE_AUDITED'),
    ('sampleCpuNs', 'sampleWallNs'),
    ('ordinarySampleMeanCpuNs', 'ordinarySampleMeanWallNs')]
for before, after in patches:
    assert before in script
    script = script.replace(before, after)
scope = {'__file__': __file__}
exec(compile(script, str(base), 'exec'), scope)
root, output = scope['root'], scope['output']
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
proof_path = root / 'callback-wall-clock/verification.json'
proof = json.loads(proof_path.read_text())
build = json.loads((output / 'build.json').read_text())
assert build['wallClockProofSha256'] == sha(proof_path)
assert build['sampleClock'] == 'CLOCK_MONOTONIC_RAW' and build['counterOrder'][7] == 'sampleWallNs'
report_path = output / 'live-profile-audit.json'
report = json.loads(report_path.read_text())
report.update(sampleClock='CLOCK_MONOTONIC_RAW', wallClockProofSha256=sha(proof_path),
    emptyMeanMedianWallNs=proof['emptyMeanMedianWallNs'], baseWallAuditorSha256=sha(base))
report['limits'].extend(['Diagnostic WALL interval includes possible host preemption; not threadCPU or exclusive body time.',
    'Empty calibration same flags/helper but different code/cache/host conditions, not exact subtractable constant.',
    'Internal helper cpu_ns legacy name does not change explicit sampleWallNs/clock metadata.'])
report_path.write_text(json.dumps(report, indent=2) + '\n')

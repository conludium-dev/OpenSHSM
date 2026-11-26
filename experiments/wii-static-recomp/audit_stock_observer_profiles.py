"""Preserve measured hotspot evidence and reject incomparable profile/FPS claims."""
from pathlib import Path
import hashlib
import json
import re

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
profiles = {}
for name, path in [('baseline-early', root / 'headless-tev-banks/host-profile-startup.txt'),
        ('baseline-late', root / 'headless-tev-banks/host-profile-video.txt'),
        ('cached-inconclusive', root / 'headless-observer-env-cache/host-profile-early.txt')]:
    text = path.read_text()
    counts = [int(value) for value in re.findall(r'^    (\d+) Thread_', text, re.M)]
    section = text.split('Sort by top of stack, same collapsed (when >= 5):', 1)[1].split('Binary Images:', 1)[0]
    leaves = {match[1].strip(): int(match[2]) for match in re.finditer(r'^\s+(.+?)  \(in [^\n]+?\)\s+(\d+)\s*$', section, re.M)}
    profiles[name] = {'sha256': sha(path), 'threadSampleCounts': counts, 'leafCounts': leaves,
        'adequateSampleCoverage': len(counts) >= 2 and min(counts) >= 1000}
assert profiles['baseline-early']['adequateSampleCoverage'] and profiles['baseline-late']['adequateSampleCoverage']
assert not profiles['cached-inconclusive']['adequateSampleCoverage']
runs = {}
for name, tag in [('baseline', 'thp-host-profile'), ('cached', 'thp-host-cached')]:
    path = root / f'headless-sc-pc-headless-{tag}-result.json'
    result = json.loads(path.read_text())
    log = root / f'headless-sc-pc-headless-{tag}.log'
    assert sha(log) == result['logSha256'] and result['deadlineReached'] and result['terminalReturncode'] == -15
    text = log.read_text(errors='replace')
    runs[name] = {'resultSha256': sha(path), 'executableSha256': result['executableSha256'],
        'decoderEntries': text.count('[CALL] 0x80209d80'), 'schedulerIdleSamples': text.count('[Sample] pc=0x8021a8e8')}
assert runs['baseline']['decoderEntries'] > 0 and runs['cached']['decoderEntries'] == 0
output = root / 'observer-env-research/host-profile-audit.json'
output.write_text(json.dumps({'result': 'HOST_DIAGNOSTIC_OVERHEAD_CONFIRMED_AFTER_RUN_INCOMPARABLE',
    'profiles': profiles, 'runs': runs, 'auditorSha256': sha(Path(__file__).resolve()),
    'limits': ['Five-second native sample requests at2ms; profiler symbol processing overhead is outside reported code sample interpretation.',
        'Baseline contains IDCT and repeated diagnostic getenv callers; cached run does not reach movie decoder and contains only2samples per thread.',
        'Do not compare leaf counts as speedup, decoder entry count as FPS or headless run as GPU/presentation proof.',
        'Cached startup/scheduler stall may be timing-sensitive; causality not established, variant not promoted.']}, indent=2) + '\n')
print('HOST_DIAGNOSTIC_OVERHEAD_CONFIRMED_AFTER_RUN_INCOMPARABLE')

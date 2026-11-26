"""Pin the one-route experimental build and terminal run; observation is not a hardware oracle."""
from pathlib import Path
from collections import Counter, deque
import hashlib
import json

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-sdk-enable-resume'
def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
original = Path(build['originalPath'])
assert sha(original) == build['originalSha256']
baseline = (output / 'baseline.cpp').read_text()
fixed = (output / 'fixed.cpp').read_text()
marker = '    {0x80217500, func_80217500},'
assert baseline.count(marker) == 1
assert fixed == baseline.replace(marker, marker + '\n    {0x8021750C, func_80217500},')
for variant in ('baseline', 'fixed'):
    record = build['records'][variant]
    for suffix, key in (('.cpp', 'sourceSha256'), ('.cpp.o', 'objectSha256'),
            ('-probe', 'executableSha256'), ('.log', 'logSha256')):
        assert sha(output / (variant + suffix)) == record[key]
for name, expected in build['retainedInputs'].items():
    assert sha(Path(name)) == expected
exe = output / 'OpenSHSMStockSDKEnableResume'
assert sha(exe) == build['executableSha256']
oracle_path = output / 'original-comparison.json'
oracle = json.loads(oracle_path.read_text())
assert oracle['buildSha256'] == sha(build_path) and len(oracle['cases']) == 7
label = 'window-sdk-enable-resume-headless-windowed-resume180'
run_path = root / (label + '-result.json')
run = json.loads(run_path.read_text()) if run_path.exists() else None
if run is not None:
    assert run['variant'] == 'window-sdk-enable-resume' and run['tag'] == 'resume180'
    assert run['terminalReturncode'] == 0 and run['deadlineReached'] and run['seconds'] == 180
    assert run['executableSha256'] == sha(exe)
log_path = root / (label + '.log')
log_hash = sha(log_path)
context = deque(maxlen=25)
first_bad_transition = []
with log_path.open(errors='replace') as stream:
    for line in stream:
        context.append(line.rstrip('\n'))
        if '[Interp] Jump to low address' in line:
            first_bad_transition = list(context)
            break
if run is not None:
    assert log_hash == run['logSha256']
capture = root / 'window-sdk-enable-resume-resume180-thp-movie-producer.jsonl'
rows = [json.loads(line) for line in capture.read_text().splitlines()]
counts = Counter(row['pc'] for row in rows)
last = {row['pc']: row for row in rows}
images = sorted(root.glob('window-sdk-enable-resume-resume180-efb*.bmp'),
    key=lambda path: int(path.stem.rsplit('_', 1)[1]))
report = {'result': 'SDK_ENABLE_RESUME_PROVENANCE_AUDIT_PASS' if run else 'SDK_ENABLE_RESUME_PARTIAL_ARTIFACT_AUDIT',
    'pid': run['pid'] if run else None, 'runResultAvailable': run is not None,
    'buildSha256': sha(build_path), 'oracleSha256': sha(oracle_path),
    'runSha256': sha(run_path) if run else None, 'logSha256': log_hash,
    'captureSha256': sha(capture), 'events': len(rows), 'logBytes': log_path.stat().st_size,
    'firstBadTransitionContext': first_bad_transition,
    'points': [{'pc': f'{pc:08X}', 'samples': counts[pc], 'lastObservedHit': last[pc]['hits'],
        'lastMovieA0Hex': last[pc]['movieA0Hex'], 'lastMovieF0Hex': last[pc]['movieF0Hex']}
        for pc in sorted(counts)],
    'finalImage': str(images[-1]) if images else None,
    'imageHashes': {str(path): sha(path) for path in images},
    'recipeSha256': sha(Path(__file__)),
    'limits': ['Missing terminal result means run lifecycle/command provenance is incomplete; never reconstruct or forge it.',
        'Exact-route change and retained link inputs proven; not a full original IRQ behavior oracle.',
        'Observer samples and sparse state changes do not pair every callback activation.',
        'Frame image must be viewed separately; a provenance audit does not prove menu or correct audio/video.']}
(output / 'audit-resume180.json').write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], len(rows), 'events')
print(json.dumps(report['points'], indent=2))
print('FINAL_IMAGE', report['finalImage'])

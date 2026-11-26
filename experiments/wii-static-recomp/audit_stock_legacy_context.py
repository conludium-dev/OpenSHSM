"""Pin corrected legacy runtime, finite verification and terminal game observations without claiming completion."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import struct
import subprocess
from stock_legacy_context_patch import adapt

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base, output = root / 'window-cache-filtered', root / 'window-legacy-context'
def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
assert (output / 'ios.cpp').read_text() == adapt((base / 'ios.cpp').read_text())
assert sha(Path('experiments/wii-static-recomp/stock_legacy_context_patch.py')) == build['adapterSha256']
assert sha(Path('experiments/wii-static-recomp/build_stock_legacy_context.py')) == build['recipeSha256']
assert sha(base / 'stock_context_observation.h') == build['contextHeaderSha256']
for name, key in [('ios.cpp', 'sourceSha256'), ('ios.cpp.o', 'objectSha256'),
    ('libnwiiruntime.a', 'archiveSha256'), ('OpenSHSMStockLegacyContext', 'executableSha256')]:
    assert sha(output / name) == build[key]
for name, expected in build['retainedLinkInputs'].items():
    assert sha(Path(name)) == expected
for member, expected in build['retainedRuntimeMembers'].items():
    data = subprocess.check_output(['/usr/bin/ar', '-p', str(output / 'libnwiiruntime.a'), member])
    assert hashlib.sha256(data).hexdigest() == expected
component_path = output / 'component.json'
component = json.loads(component_path.read_text())
assert component['buildSha256'] == sha(build_path)
assert component['probeSourceSha256'] == sha(Path('experiments/wii-static-recomp/stock_nested_context_probe.cpp'))
for variant in ('baseline', 'corrected'):
    record = component['results'][variant]
    assert sha(output / (variant + '-observed-probe')) == record['executableSha256']
    assert sha(output / (variant + '-observed.log')) == record['logSha256']
run_path = root / 'window-legacy-context-headless-windowed-legacy180-result.json'
run = json.loads(run_path.read_text())
assert run['variant'] == 'window-legacy-context' and run['tag'] == 'legacy180'
assert run['terminalReturncode'] == 0 and (run['deadlineReached'] or run['logLimitReached'])
assert run['executableSha256'] == build['executableSha256']
assert sha(Path('experiments/wii-static-recomp/run_stock_baseline.py')) == run['recipeSha256']
log = root / 'window-legacy-context-headless-windowed-legacy180.log'
assert sha(log) == run['logSha256']
capture = root / 'window-legacy-context-legacy180-thp-contexts.jsonl'
rows = [json.loads(line) for line in capture.read_text().splitlines()]
producer = root / 'window-legacy-context-legacy180-thp-movie-producer.jsonl'
movie = [json.loads(line) for line in producer.read_text().splitlines()] if producer.exists() else []
images = sorted(root.glob('window-legacy-context-legacy180-efb_*.bmp'),
    key=lambda path: int(path.stem.rsplit('_', 1)[1]))
report = {'result': 'LEGACY_CONTEXT_PROVENANCE_AUDIT_PASS', 'pid': run['pid'],
    'buildSha256': sha(build_path), 'componentSha256': sha(component_path), 'runSha256': sha(run_path),
    'logSha256': sha(log), 'logBytes': log.stat().st_size, 'captureSha256': sha(capture),
    'events': len(rows), 'stageCounts': dict(Counter(row['stage'] for row in rows)),
    'zeroLoadRows': [row for row in rows if row['stage'] == 3 and row['pc'] == 0],
    'movieCaptureSha256': sha(producer) if producer.exists() else None,
    'movieEvents': len(movie), 'moviePointCounts': {f'{key:08X}': value for key, value in Counter(row['pc'] for row in movie).items()},
    'observedF4Values': sorted({struct.unpack_from('>I', bytes.fromhex(row['movieF0Hex']), 4)[0] for row in movie}),
    'lastMovieRows': movie[-6:], 'finalImage': str(images[-1]) if images else None,
    'imageHashes': {str(path): sha(path) for path in images}, 'recipeSha256': sha(Path(__file__)),
    'limits': ['Finite selection and original SDK tail checks are not full nested IRQ/physical Wii behavior acceptance.',
        'Context/producer caps and sampling still limit absence/activation claims.',
        'Image/audio/menu acceptance requires separate inspection; terminal0 test stop is not game completion.']}
(output / 'audit-legacy180.json').write_text(json.dumps(report, indent=2) + '\n')
print('LEGACY_CONTEXT_PROVENANCE_AUDIT_PASS', len(rows), 'contexts', len(movie), 'movie records')
print('F4', report['observedF4Values'][-10:])
print('FINAL_IMAGE', report['finalImage'])

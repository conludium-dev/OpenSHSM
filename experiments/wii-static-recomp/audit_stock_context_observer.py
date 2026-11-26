"""Pin current observer build, finite component and terminal owned run; retain raw context provenance."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess
import argparse
from stock_cache_observation import extend_header, adapt_guest, verify_sites

parser = argparse.ArgumentParser()
parser.add_argument('--cache', action='store_true')
parser.add_argument('--filtered-cache', action='store_true')
parser.add_argument('--component-only', action='store_true')
args = parser.parse_args()
args.cache = args.cache or args.filtered_cache
variant = 'window-cache-filtered' if args.filtered_cache else 'window-cache-observe' if args.cache else 'window-context-observe'
tag = 'filtered180' if args.filtered_cache else 'cache180' if args.cache else 'ctx180'

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / variant
def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for name, key in [('ios.cpp', 'sourceSha256'), ('ios.cpp.o', 'objectSha256'),
        ('libnwiiruntime.a', 'archiveSha256'), ('OpenSHSMStockCacheFiltered' if args.filtered_cache else 'OpenSHSMStockCacheObserver' if args.cache else 'OpenSHSMStockContextObserver', 'executableSha256'),
        ('context-observer-probe', 'probeSha256'), ('component-contexts.jsonl', 'componentCaptureSha256')]:
    assert sha(output / name) == build[key]
header = output / 'stock_context_observation.h' if args.cache else Path('experiments/wii-static-recomp/stock_context_observation.h')
assert sha(header) == build['headerSha256']
if args.cache:
    assert header.read_text() == extend_header(Path('experiments/wii-static-recomp/stock_context_observation.h').read_text(), args.filtered_cache)
    assert build['cacheAdapterSha256'] == sha(Path('experiments/wii-static-recomp/stock_cache_observation.py'))
    verify_sites(Path('work/private-game/disc/DATA/sys/main.dol').read_bytes())
    for name, facts in build['guestChanges'].items():
        original = Path(facts['originalPath'])
        assert sha(original) == facts['originalSha256']
        assert (output / name).read_text() == adapt_guest(original.read_text(), int(name.split('_')[1].split('.')[0]))
        assert sha(output / name) == facts['sourceSha256'] and sha(output / (name + '.o')) == facts['objectSha256']
    assert sha(output / 'cache-component-contexts.jsonl') == build['cacheComponent']['captureSha256']
    assert sha(output / 'cache-probe') == build['cacheComponent']['executableSha256']
    helper_path = output / 'helper-component.json'
    helper = json.loads(helper_path.read_text())
    assert helper['buildSha256'] == sha(build_path) and helper['events'] == 533
    assert helper['sourceSha256'] == sha(Path('experiments/wii-static-recomp/stock_cache_observation_contract.cpp'))
    for path, key in [('capturePath', 'captureSha256'), ('executablePath', 'executableSha256'), ('logPath', 'logSha256')]:
        assert sha(Path(helper[path])) == helper[key]
assert sha(Path('experiments/wii-static-recomp/build_stock_context_observer.py')) == build['recipeSha256']
for name, expected in build['retainedLinkInputs'].items():
    assert sha(Path(name)) == expected
for member, expected in build['retainedRuntimeMembers'].items():
    data = subprocess.check_output(['/usr/bin/ar', '-p', str(output / 'libnwiiruntime.a'), member])
    assert hashlib.sha256(data).hexdigest() == expected
fixture = [json.loads(line) for line in (output / 'component-contexts.jsonl').read_text().splitlines()]
assert len(fixture) == 24 and sum(row['stage'] == 3 and row['pc'] == 0 for row in fixture) == 4
if args.component_only:
    (output / 'audit-components.json').write_text(json.dumps({'result': 'CONTEXT_OBSERVER_COMPONENT_PROVENANCE_PASS',
        'buildSha256': sha(build_path), 'filteredCache': args.filtered_cache,
        'helperComponentSha256': sha(output / 'helper-component.json') if args.cache else None,
        'runtimeMembersRetained': len(build['retainedRuntimeMembers']),
        'limits': ['Component provenance only; no game run, image/audio/IRQ/menu acceptance.']}, indent=2) + '\n')
    print('CONTEXT_OBSERVER_COMPONENT_PROVENANCE_PASS; game launch NOT verified')
    raise SystemExit(0)
label = variant + '-headless-windowed-' + tag
run_path = root / (label + '-result.json')
run = json.loads(run_path.read_text())
assert run['variant'] == variant and run['tag'] == tag
assert run['terminalReturncode'] == 0 and (run['deadlineReached'] or run['logLimitReached'])
assert run['executableSha256'] == build['executableSha256']
assert run['recipeSha256'] == sha(Path('experiments/wii-static-recomp/run_stock_baseline.py'))
log = root / (label + '.log')
assert sha(log) == run['logSha256']
capture = root / (variant + '-' + tag + '-thp-contexts.jsonl')
rows = [json.loads(line) for line in capture.read_text().splitlines()]
assert len(rows) <= (7184 if args.cache else 4096) and [row['serial'] for row in rows] == list(range(len(rows)))
def context_fields(row, key):
    data = bytes.fromhex(row[key])
    if len(data) != 0x1C8:
        return None
    word = lambda offset: struct.unpack_from('>I', data, offset)[0]
    return {'sp': f'{word(4):08X}', 'lr': f'{word(0x84):08X}', 'srr0': f'{word(0x198):08X}',
        'srr1': f'{word(0x19C):08X}', 'state': f'{struct.unpack_from(">H", data, 0x1A2)[0]:04X}'}
zeros = [row for row in rows if row['stage'] == 3 and row['pc'] == 0]
cache_context_matches = []
for before, after in zip(rows, rows[1:]):
    if before['stage'] == 0 and after['stage'] == 3 and before['pc'] == 0x80212FC4 and before['lr'] == 0x8009BB9C:
        keys = ['pc', 'lr', 'sp', 'ctr', 'gpr3', 'gpr4', 'gpr5', 'selected']
        cache_context_matches.append({'beforeSerial': before['serial'], 'afterSerial': after['serial'],
            'equalFields': [key for key in keys if before.get(key) == after.get(key)],
            'limits': 'Adjacent matching snapshots, not complete IRQ activation pairing or all context fields.'})
images = sorted(root.glob(variant + '-' + tag + '-efb_*.bmp'),
    key=lambda path: int(path.stem.rsplit('_', 1)[1]))
report = {'result': 'CONTEXT_OBSERVER_PROVENANCE_AUDIT_PASS', 'pid': run['pid'],
    'buildSha256': sha(build_path), 'runSha256': sha(run_path), 'logSha256': sha(log),
    'captureSha256': sha(capture), 'events': len(rows), 'capReached': len(rows) == (7184 if args.cache else 4096),
    'stageCounts': {str(stage): sum(row['stage'] == stage for row in rows) for stage in range(9 if args.cache else 4)},
    'cacheRows': [row for row in rows if row['stage'] >= 4],
    'adjacentCacheContextMatches': cache_context_matches,
    'stageBudgetsPossiblyReached': [stage for stage in range(9) if args.cache
        and sum(row['stage'] == stage for row in rows) >= (512 if stage < 4 else 1024)],
    'helperComponentSha256': sha(output / 'helper-component.json') if args.cache else None,
    'zeroLoadRows': zeros,
    'zeroLoadContexts': [{'serial': row['serial'], 'selected': context_fields(row, 'selectedHex'),
        'current': context_fields(row, 'currentHex'), 'saved': context_fields(row, 'savedHex')} for row in zeros],
    'lastRows': rows[-12:], 'finalImage': str(images[-1]) if images else None,
    'imageHashes': {str(path): sha(path) for path in images}, 'recipeSha256': sha(Path(__file__)),
    'limits': ['Read-only selection/save/load snapshots only, not complete context-write or IRQ activation pairing.',
        'Cap and sampling can hide transitions; absence does not establish missing execution.',
        'Native observer fixture and original software PPC kernels are not physical Wii behavior acceptance.',
        'Image must be viewed separately; terminal0 after test stop does not mean game completed.']}
(output / ('audit-' + tag + '.json')).write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], len(rows), 'events; zero restores', len(zeros))
print(json.dumps(report['zeroLoadContexts'], indent=2))
print('FINAL_IMAGE', report['finalImage'])

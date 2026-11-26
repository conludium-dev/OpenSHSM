"""Audit original update-boundary observations without inferring complete activation pairing."""
from pathlib import Path
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import re
from stock_thp_update_observation import adapt

parser = argparse.ArgumentParser()
parser.add_argument('--tag', required=True)
args = parser.parse_args()
assert re.fullmatch('[a-z0-9-]{1,40}', args.tag)
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-movie-update'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert build['baseBuildSha256'] == sha(root / 'window-movie-queues/build.json')
original = Path(build['originalPath'])
assert sha(original) == build['originalSourceSha256']
dol = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
assert (output / 'output_11.cpp').read_text() == adapt(original.read_text(), dol.read_bytes())
for name, field in [('output_11.cpp', 'sourceSha256'), ('output_11.cpp.o', 'objectSha256'),
    ('OpenSHSMStockMovieUpdate', 'executableSha256')]:
    assert sha(output / name) == build[field]
assert sha(Path('experiments/wii-static-recomp/stock_thp_update_observation.h')) == build['headerSha256']
assert sha(Path('experiments/wii-static-recomp/stock_thp_queue_observation.h')) == build['queueHeaderSha256']
for path, digest in build['retainedInputs'].items():
    assert sha(Path(path)) == digest
component = json.loads((output / 'component.json').read_text())
assert component['result'] == 'MOVIE_UPDATE_HELPER_COMPONENT_PASS' and component['events'] == 4
assert component['buildSha256'] == sha(output / 'build.json')
assert sha(Path('experiments/wii-static-recomp/stock_thp_update_contract.cpp')) == component['sourceSha256']
for name, field in [('observer-contract', 'executableSha256'), ('contract.cpp.o', 'objectSha256'),
    ('component-movie-update.jsonl', 'captureSha256'), ('contract.log', 'logSha256')]:
    assert sha(output / name) == component[field]
label = 'window-movie-update-headless-windowed-' + args.tag
run_path, log_path = root / (label + '-result.json'), root / (label + '.log')
run = json.loads(run_path.read_text())
assert run['executableSha256'] == build['executableSha256'] and run['logSha256'] == sha(log_path)
assert run['recipeSha256'] == sha(Path('experiments/wii-static-recomp/run_stock_baseline.py'))
assert run['originalDolSha256'] == sha(dol)
prefix = root / ('window-movie-update-' + args.tag + '-thp')
capture = Path(str(prefix) + '-movie-update.jsonl')
rows = [json.loads(line) for line in capture.read_text().splitlines()] if capture.exists() else []
groups = defaultdict(list)
for index, row in enumerate(rows):
    assert row['serial'] == index
    assert row['pc'] in (0x8009B72C, 0x8009B750, 0x8009B760, 0x8009B770)
    assert row['activeValid'] and row['active'] == int(row['stateF0Hex'][16:24], 16)
    groups[row['pc']].append(row)
summary = [{'pc': f'{pc:08X}', 'samples': len(items), 'lastObservedHit': items[-1]['hits'],
    'candidates': dict(Counter(f'{row["candidate"]:08X}' for row in items)),
    'activeBuffers': dict(Counter(f'{row["active"]:08X}' for row in items)), 'last': items[-1]}
    for pc, items in groups.items()]
log = log_path.read_text(errors='replace')
report = {'result': 'MOVIE_UPDATE_OBSERVER_PROVENANCE_AUDIT_PASS', 'events': len(rows),
    'coverage': 'OBSERVED' if rows else 'NOT_REACHED', 'eventCapReached': len(rows) == 4096, 'groups': summary,
    'buildSha256': sha(output / 'build.json'), 'componentSha256': sha(output / 'component.json'),
    'runSha256': sha(run_path), 'captureSha256': sha(capture) if capture.exists() else None,
    'terminalReturncode': run['terminalReturncode'], 'deadlineReached': run['deadlineReached'],
    'decoderCalls': len(re.findall(r'\[CALL\] 0x80209d80 ', log)),
    'statistics': re.findall(r'\[STAT\] (\d+)s frames=(\d+) draws=(\d+)', log),
    'captures': {str(path): sha(path) for path in root.glob('window-movie-update-' + args.tag + '-efb_*.bmp')},
    'otherObservationFiles': {str(path): sha(path) for path in root.glob('window-movie-update-' + args.tag + '-thp-*')},
    'limits': build['limits'] + component['limits']}
(output / ('audit-' + args.tag + '.json')).write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], 'events', len(rows))
print(json.dumps([{key: group[key] for key in ('pc', 'samples', 'lastObservedHit', 'candidates', 'activeBuffers')}
    for group in summary], indent=2))

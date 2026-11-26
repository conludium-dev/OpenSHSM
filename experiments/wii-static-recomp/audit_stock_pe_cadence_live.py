"""Match observational command IDs across copy cutoff and real Render brackets."""
from pathlib import Path
import argparse
import collections
import hashlib
import json
import re
import statistics

parser = argparse.ArgumentParser()
parser.add_argument('--artifacts', type=Path, required=True)
args = parser.parse_args()
artifacts = args.artifacts.resolve()
assert artifacts.parent == Path('/private/tmp') and re.fullmatch(r'openshsm-run-[A-Za-z0-9_-]+', artifacts.name)
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
root = Path(__file__).resolve().parents[2] / 'work/private-game/static-recomp/stock-baseline'
build_path = root / 'window-pe-cadence/build.json'
component_path = build_path.parent / 'component-verification.json'
build = json.loads(build_path.read_text())
component = json.loads(component_path.read_text())
assert component['buildSha256'] == sha(build_path)
assert component['result'] == 'PE_CADENCE_GPU16_SETTINGS3_RETAINED_PARENT_COMPONENTS_VERIFIED'
run_path = artifacts / 'headless-sc-pc-headless-windowed-pe-cadence-live-result.json'
run = json.loads(run_path.read_text())
assert run['terminalReturncode'] == 0 and run['deadlineReached'] and run['temporaryEvidence']
assert Path(run['artifactDirectory']) == artifacts and run['peCadenceAfterMs'] == 120000
assert run['executableSha256'] == build['executableSha256'] == sha(build['executablePath'])
log = artifacts / 'headless-sc-pc-headless-windowed-pe-cadence-live.log'
assert sha(log) == run['logSha256']
text = log.read_text()
batches = {}
rendered = {}
markers = collections.defaultdict(list)
for line in text.splitlines():
    if not line.startswith('[PECadence'):
        continue
    values = {key: int(value) for key, value in re.findall(r'(\w+)=(-?\d+)', line)}
    batch = values['batch']
    if line.startswith('[PECadenceBatch]'):
        assert batch not in batches
        batches[batch] = values
    elif line.startswith('[PECadenceRendered]'):
        assert batch not in rendered
        rendered[batch] = values
    elif line.startswith('[PECadenceMarker]'):
        assert values['selected'] in (0, 1) and values['reg'] in (0x45, 0x47, 0x48)
        markers[values['command']].append(values)
    else:
        raise AssertionError(line)
assert batches and len(batches) <= 128 and sum(map(len, markers.values())) <= 512
assert all(a < b for a, b in zip(batches, list(batches)[1:]))
for batch, end in rendered.items():
    assert batch in batches and batches[batch]['end'] >= 0
    assert end['hostUs'] >= batches[batch]['hostUs']
pairs = []
unresolved = []
for command, observations in markers.items():
    assert len({(row['reg'], row['value']) for row in observations}) == 1
    for row in observations:
        assert row['batch'] in batches and row['hostUs'] == batches[row['batch']]['hostUs']
        if row['selected']:
            assert row['batch'] in rendered
    deferred = [row for row in observations if not row['selected']]
    selected = [row for row in observations if row['selected']]
    assert len(selected) <= 1
    if not deferred:
        continue
    first = deferred[0]
    if not selected:
        unresolved.append(command)
        continue
    applied = selected[0]
    assert applied['batch'] > first['batch']
    assert batches[first['batch']]['copy'] >= 0 and first['batch'] in rendered
    pairs.append({'command': command, 'reg': first['reg'], 'value': first['value'],
        'deferredBatch': first['batch'], 'selectedBatch': applied['batch'],
        'hostPassesDeferred': applied['batch'] - first['batch'],
        'signalDelayLowerUs': applied['hostUs'] - first['hostUs'],
        'signalDelayUpperUs': rendered[applied['batch']]['hostUs'] - first['hostUs'],
        'copyRenderedToNextBatchUs': applied['hostUs'] - rendered[first['batch']]['hostUs']})
copies = [batch for batch, row in batches.items() if row['copy'] >= 0]
copy_steps = [b - a for a, b in zip(copies, copies[1:])]
counts = collections.Counter('copy' if row['copy'] >= 0 else 'completion' if row['end'] >= 0 else 'incomplete'
    for row in batches.values())
summary = {'batches': len(batches), 'renderedBatches': len(rendered), 'batchKinds': dict(counts),
    'markerRecords': sum(map(len, markers.values())), 'uniqueMarkers': len(markers),
    'pairedDeferredMarkers': len(pairs), 'unresolvedDeferredMarkers': len(unresolved),
    'copyHostPassStepMedian': statistics.median(copy_steps) if copy_steps else None}
if pairs:
    for key in ['hostPassesDeferred', 'signalDelayLowerUs', 'signalDelayUpperUs', 'copyRenderedToNextBatchUs']:
        summary[key + 'Median'] = statistics.median(row[key] for row in pairs)
report = {'result': 'OWNED_PE_CADENCE_COMMAND_ID_RENDER_BRACKETS_AUDITED',
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), build_path, component_path, run_path, log]},
    'summary': summary, 'pairs': pairs, 'unresolvedCommandIds': unresolved,
    'limits': ['Signal occurs within existing Render bracket; lower/upper discovery-to-signal bounds, not exact hardware acknowledgement time.',
        'Deferred IDs prove existing-carry delay; do not prove decoder-exclusive bottleneck or safe removal of sleeps.',
        'Observer logs may perturb execution; bounded late sample, not whole-game physical Wii oracle.']}
path = artifacts / 'pe-cadence-audit.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
print(json.dumps(summary, indent=2))

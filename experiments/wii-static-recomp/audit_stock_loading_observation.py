"""Audit exact loading hooks and summarize actual callback/main-loop progress without inventing readiness."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import struct
from stock_loading_observation import adapt

parser = argparse.ArgumentParser()
parser.add_argument('--tag')
parser.add_argument('--payloads', action='store_true')
args = parser.parse_args()
assert args.tag is None or re.fullmatch('[a-z0-9-]{1,40}', args.tag)
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base = root / 'window-scan-consume'
variant = 'window-loading-payload' if args.payloads else 'window-loading-observe'
output = root / variant
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert build['baseBuildSha256'] == sha(base / 'build.json')
dol = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
for item in build['compiled']:
    name = f'output_{item["index"]}.cpp'
    original = Path(item['originalPath'])
    assert sha(original) == item['originalSha256']
    assert (output / name).read_text() == adapt(original.read_text(), dol.read_bytes(), item['index'], args.payloads)
    assert sha(output / name) == item['sourceSha256'] and sha(output / (name + '.o')) == item['objectSha256']
assert sha(Path('experiments/wii-static-recomp/stock_loading_observation.h')) == build['headerSha256']
assert sha(output / ('OpenSHSMStockLoadingPayload' if args.payloads else 'OpenSHSMStockLoadingObserver')) == build['executableSha256']
if args.payloads:
    assert build['payloadHeaderSha256'] == sha(Path('experiments/wii-static-recomp/stock_loading_payload_observation.h'))
for path, digest in build['retainedInputs'].items():
    assert sha(Path(path)) == digest
component = json.loads((output / 'component.json').read_text())
assert component['result'] == 'LOADING_OBSERVER_HELPER_COMPONENT_PASS'
assert component['buildSha256'] == sha(output / 'build.json')
assert component['headerSha256'] == build['headerSha256']
assert component['sourceSha256'] == sha(Path('experiments/wii-static-recomp/' + ('stock_loading_payload_contract.cpp' if args.payloads else 'stock_loading_observation_contract.cpp')))
if args.payloads:
    assert component['baseContractSha256'] == sha(Path('experiments/wii-static-recomp/stock_loading_observation_contract.cpp'))
    assert component['payloadHeaderSha256'] == build['payloadHeaderSha256']
    assert (output / 'component-payload0.bin').read_bytes() == bytes(range(100, 116))
    assert not (output / 'component-payload1.bin').exists()
assert component['objectSha256'] == sha(output / 'contract.cpp.o')
assert component['executableSha256'] == sha(output / 'observer-contract')
assert component['captureSha256'] == sha(output / 'component-loading.jsonl')
assert component['logSha256'] == sha(output / 'contract.log')
for path, digest in component['linkInputs'].items():
    assert sha(Path(path)) == digest
report = {'result': 'READ_ONLY_LOADING_OBSERVER_AUDIT_PASS', 'component': component['result'],
    'limits': build['limits'] + component['limits']}
if args.tag:
    prefix = root / (variant + '-headless-windowed-' + args.tag)
    run_path, log_path = Path(str(prefix) + '-result.json'), Path(str(prefix) + '.log')
    run = json.loads(run_path.read_text())
    assert run['executableSha256'] == build['executableSha256'] and run['logSha256'] == sha(log_path)
    assert run['originalDolSha256'] == sha(dol) and run['recipeSha256'] == sha(Path('experiments/wii-static-recomp/run_stock_baseline.py'))
    capture = root / (variant + '-' + args.tag + '-thp-loading.jsonl')
    rows = [json.loads(line) for line in capture.read_text().splitlines()]
    assert rows and all(len(row['queueHex']) == 32 and len(row['gateHex']) == 2 for row in rows)
    assert all(rows[i]['hostMs'] <= rows[i + 1]['hostMs'] for i in range(len(rows) - 1))
    before = {row['id']: row for row in rows if row['event'] == 'callback-before'}
    after = {row['id']: row for row in rows if row['event'] == 'callback-after'}
    assert len(before) == sum(row['event'] == 'callback-before' for row in rows)
    assert len(after) == sum(row['event'] == 'callback-after' for row in rows)
    assert set(after).issubset(before)
    completed = []
    for id, finish in after.items():
        start = before[id]
        assert all(start[key] == finish[key] for key in ('sp', 'request', 'callback'))
        completed.append({'id': id, 'callback': f'{start["callback"]:08X}', 'hostDurationMs': finish['hostMs'] - start['hostMs']})
    pending = [row for id, row in before.items() if id not in after]
    log = log_path.read_text(errors='replace')
    report['runtime'] = {'runSha256': sha(run_path), 'captureSha256': sha(capture),
        'terminalReturncode': run['terminalReturncode'], 'deadlineReached': run['deadlineReached'],
        'decoderCalls': len(re.findall(r'\[CALL\] 0x80209d80 ', log)), 'gpuHang': 'GPU Hang' in log,
        'statistics': re.findall(r'\[STAT\] (\d+)s frames=(\d+) draws=(\d+)', log),
        'captures': {str(path): sha(path) for path in sorted(root.glob(variant + '-' + args.tag + '-efb_*.bmp'))}}
    if args.payloads:
        payload_metadata = root / (variant + '-' + args.tag + '-thp-payloads.jsonl')
        records = [json.loads(line) for line in payload_metadata.read_text().splitlines()]
        assert len(records) <= 16 and len({row['id'] for row in records}) == len(records)
        hashes = {}
        for row in records:
            start = before[row['id']]
            assert row['request'] == start['request'] and row['callback'] == start['callback']
            assert (row['address'], row['size']) == tuple(start['gpr3to7'][2:4])
            path = root / (variant + '-' + args.tag + '-thp-payload' + str(row['id']) + '.bin')
            assert path.stat().st_size == row['size'] <= 1024 * 1024
            hashes[str(path)] = sha(path)
        report['payloads'] = {'metadataSha256': sha(payload_metadata), 'records': records, 'fileHashes': hashes,
            'limit': 'Private copies of original RAM payload bytes; resource identity requires independent source byte comparison.'}
    report['loading'] = {'events': len(rows), 'callbacksStarted': len(before), 'callbacksFinished': len(after),
        'captureCapReached': len(before) == 512, 'completed': completed, 'pendingAtDeadline': pending,
        'frameBoundaries': [row for row in rows if row['event'].startswith('frame-')],
        'lastEvent': rows[-1], 'queueCounts': sorted({struct.unpack('>4I', bytes.fromhex(row['queueHex']))[1] for row in rows})}
    report['limits'].append('Unreturned at bounded deadline is not permanent deadlock proof; retained field words and callback addresses do not name assets or imply callback semantics.')
    report['limits'].append('Pending means no paired return observed: unmatched return hooks are omitted; pairing is not complete control-flow/IRQ proof. Post-callback request memory may already be freed or reused.')
(output / ('audit-' + (args.tag or 'component') + '.json')).write_text(json.dumps(report, indent=2) + '\n')
print(report['result'])
if args.tag:
    print({key: report['loading'][key] for key in ('events', 'callbacksStarted', 'callbacksFinished', 'captureCapReached', 'pendingAtDeadline', 'queueCounts')})

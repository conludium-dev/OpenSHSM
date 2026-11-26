"""Audit the original common decimal-reader observer and identify bounded unreturned calls."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import struct
from stock_numeric_reader import adapt, flight_header

parser = argparse.ArgumentParser()
parser.add_argument('--tag')
parser.add_argument('--flight', action='store_true')
args = parser.parse_args()
assert args.tag is None or re.fullmatch('[a-z0-9-]{1,40}', args.tag)
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base = root / 'window-subtitle-progress'
variant = 'window-numeric-flight' if args.flight else 'window-numeric-reader'
output = root / variant
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert build['baseBuildSha256'] == sha(base / 'build.json')
original = Path(build['originalPath'])
assert sha(original) == build['originalSha256']
dol = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
assert (output / 'output_31.cpp').read_text() == adapt(original.read_text(), dol.read_bytes(), args.flight)
assert sha(output / 'output_31.cpp') == build['sourceSha256'] and sha(output / 'output_31.cpp.o') == build['objectSha256']
assert sha(Path('experiments/wii-static-recomp/stock_numeric_reader.h')) == build['headerSha256']
assert sha(output / ('OpenSHSMStockNumericFlight' if args.flight else 'OpenSHSMStockNumericReader')) == build['executableSha256']
if args.flight:
    assert (output / 'stock_numeric_reader_flight.h').read_text() == flight_header(Path('experiments/wii-static-recomp/stock_numeric_reader.h').read_text())
    assert build['flightHeaderSha256'] == sha(output / 'stock_numeric_reader_flight.h')
for path, digest in build['retainedInputs'].items():
    assert sha(Path(path)) == digest
component = json.loads((output / 'component.json').read_text())
assert component['result'] == 'READ_ONLY_SCAN_OBSERVER_COMPONENT_PASS' and component['cases'] == 20
assert component['buildSha256'] == sha(output / 'build.json') and component['probeBuildSha256'] == sha(output / 'probe-build.json')
assert component['captureSha256'] == sha(output / 'component-scan.jsonl')
assert component['logSha256'] == sha(output / 'component.log')
component_reader = output / 'component-numeric-reader.jsonl'
test_rows = [json.loads(line) for line in component_reader.read_text().splitlines()]
assert sum(row['before'] for row in test_rows) == sum(not row['before'] for row in test_rows) == 8
report = {'result': 'READ_ONLY_NUMERIC_READER_AUDIT_PASS', 'regressionCases': 20, 'componentReaderPairs': 8,
    'componentReaderCaptureSha256': sha(component_reader), 'limits': build['limits'] + component['limits']}
if args.flight:
    assert json.loads((output / 'component-numeric-flight.json').read_text()) == {'started': 8, 'finished': 8, 'overwrittenActive': 0, 'pending': []}
if args.tag:
    prefix = root / (variant + '-headless-windowed-' + args.tag)
    run_path, log_path = Path(str(prefix) + '-result.json'), Path(str(prefix) + '.log')
    run = json.loads(run_path.read_text())
    assert run['executableSha256'] == build['executableSha256'] and run['logSha256'] == sha(log_path)
    assert run['originalDolSha256'] == sha(dol) and run['recipeSha256'] == sha(Path('experiments/wii-static-recomp/run_stock_baseline.py'))
    capture = root / (variant + '-' + args.tag + '-thp-numeric-reader.jsonl')
    rows = [json.loads(line) for line in capture.read_text().splitlines()]
    before = {row['id']: row for row in rows if row['before']}
    after = {row['id']: row for row in rows if not row['before']}
    assert len(before) == sum(row['before'] for row in rows) and len(after) == sum(not row['before'] for row in rows)
    assert set(after).issubset(before)
    complete = []
    for id, finish in after.items():
        start = before[id]
        assert (start['sp'], start['caller']) == (finish['sp'], finish['caller'])
        text = bytes.fromhex(start['inputHex']).decode('ascii')
        number = re.match(r'\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)', text)
        expected = struct.pack('>d', float(number[1])).hex() if number else None
        complete.append({'id': id, 'input': text, 'caller': f'{start["caller"]:08X}',
            'hostDurationMs': finish['hostMs'] - start['hostMs'], 'msr': f'{finish["msr"]:08X}',
            'expected': expected, 'actual': finish['fpr1Hex'],
            'logicalMatch': expected == finish['fpr1Hex'] if expected is not None and finish['msr'] & 0x2000 else None})
    pending = [dict(row, input=bytes.fromhex(row['inputHex']).decode('ascii')) for id, row in before.items() if id not in after]
    log = log_path.read_text(errors='replace')
    report['runtime'] = {'runSha256': sha(run_path), 'captureSha256': sha(capture),
        'terminalReturncode': run['terminalReturncode'], 'deadlineReached': run['deadlineReached'],
        'decoderCalls': len(re.findall(r'\[CALL\] 0x80209d80 ', log)), 'gpuHang': 'GPU Hang' in log,
        'statistics': re.findall(r'\[STAT\] (\d+)s frames=(\d+) draws=(\d+)', log),
        'captures': {str(path): sha(path) for path in sorted(root.glob(variant + '-' + args.tag + '-efb_*.bmp'))}}
    report['reader'] = {'started': len(before), 'finished': len(after), 'capReached': len(before) == 8192,
        'pendingAtDeadline': pending, 'completed': complete, 'lastRow': rows[-1],
        'logicalMismatches': [row for row in complete if row['logicalMatch'] is False]}
    if args.flight:
        summary_path = root / (variant + '-' + args.tag + '-thp-numeric-flight.json')
        summary = json.loads(summary_path.read_text())
        assert summary['started'] >= len(before) and summary['finished'] >= len(after)
        assert summary['started'] >= summary['finished']
        for row in summary['pending']:
            row['input'] = bytes.fromhex(row['inputHex']).decode('ascii')
        report['flight'] = dict(summary, captureSha256=sha(summary_path))
    report['limits'].append('No paired return at deadline does not prove permanent loop; raw FPR bank/MSR.FP and80byte input prefix limit logical comparison, not original hardware oracle.')
(output / ('audit-' + (args.tag or 'component') + '.json')).write_text(json.dumps(report, indent=2) + '\n')
print(report['result'])
if args.tag:
    print({key: report['reader'][key] for key in ('started', 'finished', 'capReached', 'pendingAtDeadline', 'logicalMismatches')})

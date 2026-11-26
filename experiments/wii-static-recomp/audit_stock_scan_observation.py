"""Audit observer provenance and compare captured finite UI values with an independent logical reference."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import struct
from stock_scan_observation import adapt
from stock_scan_consumption import adapt_caller, adapt_interpreter, IMPLEMENTATION

parser = argparse.ArgumentParser()
parser.add_argument('--tag')
parser.add_argument('--consumption', action='store_true')
args = parser.parse_args()
assert args.tag is None or re.fullmatch('[a-z0-9-]{1,40}', args.tag)
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base = root / 'window-scan-routes'
variant = 'window-scan-consume' if args.consumption else 'window-scan-observe'
output = root / variant
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert build['baseBuildSha256'] == sha(base / 'build.json')
dol = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
assert (output / 'output_31.cpp').read_text() == adapt((base / 'output_31.cpp').read_text(), dol.read_bytes()) + (IMPLEMENTATION if args.consumption else '')
assert build['sourceSha256'] == sha(output / 'output_31.cpp')
assert build['objectSha256'] == sha(output / 'output_31.cpp.o')
assert build['headerSha256'] == sha(Path('experiments/wii-static-recomp/stock_scan_observation.h'))
assert build['executableSha256'] == sha(output / ('OpenSHSMStockScanConsumer' if args.consumption else 'OpenSHSMStockScanObserver'))
if args.consumption:
    caller = build['caller']
    assert sha(Path(caller['originalPath'])) == caller['originalSha256']
    assert (output / 'output_19.cpp').read_text() == adapt_caller(Path(caller['originalPath']).read_text(), dol.read_bytes())
    assert sha(output / 'output_19.cpp') == caller['sourceSha256'] and sha(output / 'output_19.cpp.o') == caller['objectSha256']
    assert build['consumptionHeaderSha256'] == sha(Path('experiments/wii-static-recomp/stock_scan_consumption.h'))
    runtime = build['runtime']
    assert sha(Path(runtime['originalPath'])) == runtime['originalSha256']
    assert (output / 'interpreter.cpp').read_text() == adapt_interpreter((root / 'window-fp-guard/interpreter.cpp').read_text())
    assert sha(output / 'interpreter.cpp') == runtime['sourceSha256'] and sha(output / 'interpreter.cpp.o') == runtime['objectSha256']
    assert sha(output / 'libnwiiruntime.a') == runtime['archiveSha256']
    import subprocess
    for member, digest in runtime['retainedMembers'].items():
        assert hashlib.sha256(subprocess.check_output(['/usr/bin/ar', '-p', str(output / 'libnwiiruntime.a'), member])).hexdigest() == digest
for path, digest in build['retainedInputs'].items():
    assert sha(Path(path)) == digest
component = json.loads((output / 'component.json').read_text())
assert component['result'] == 'READ_ONLY_SCAN_OBSERVER_COMPONENT_PASS' and component['cases'] == 20
assert component['buildSha256'] == sha(output / 'build.json')
assert component['probeBuildSha256'] == sha(output / 'probe-build.json')
assert component['captureSha256'] == sha(output / 'component-scan.jsonl')
assert component['logSha256'] == sha(output / 'component.log')
assert component['scriptSha256'] == sha(Path('experiments/wii-static-recomp/' + ('verify_stock_scan_consumption.py' if args.consumption else 'verify_stock_scan_observation.py')))
probe = json.loads((output / 'probe-build.json').read_text())
assert probe['executableSha256'] == sha(output / 'scan-probe')
for path, digest in probe['linkInputs'].items():
    assert sha(Path(path)) == digest
report = {'result': 'READ_ONLY_SCAN_OBSERVER_AUDIT_PASS', 'componentCases': 20,
    'limits': build['limits'] + component['limits']}
original = dol.read_bytes()
layout = struct.unpack('>64I', original[:256])
caller_evidence = []
for name, start, end in [('auto_03_80100D70_text.s', 0x80101644, 0x8010168C),
    ('auto_03_8010EE1C_text.s', 0x8010F0E4, 0x8010F130)]:
    path = root.parent / 'dtk-output/asm' / name
    words = [(int(address, 16), int(raw.replace(' ', ''), 16)) for address, raw in
        re.findall(r'/\* ([0-9A-F]{8}) [0-9A-F]{8}  ([0-9A-F ]{11}) \*/', path.read_text())
        if start <= int(address, 16) < end]
    assert [address for address, _ in words] == list(range(start, end, 4))
    for address, word in words:
        section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
        assert struct.unpack_from('>I', original, layout[section] + address - layout[18 + section])[0] == word
    caller_evidence.append({'assemblySha256': sha(path), 'start': f'{start:08X}', 'end': f'{end:08X}', 'words': len(words)})
report['callerEvidence'] = caller_evidence
if args.consumption:
    section = next(i for i in range(18) if layout[18 + i] <= 0x8052CE5C < layout[18 + i] + layout[36 + i])
    assert struct.unpack_from('>I', original, layout[section] + 0x8052CE5C - layout[18 + section])[0] == 0x42700000
    report['timeFactorOriginal'] = '8052CE5C:42700000 = float32 60'
report['callerLimit'] = 'Original time-combine store80101688 and rectangle stores8010F114/11C/124/12C identified statically; live destination consumption not captured.'
if args.consumption:
    report['callerLimit'] = 'Static caller evidence; separate consumerComparison verifies live captured destinations, not full original floating/IRQ behavior.'
if args.tag:
    prefix = root / (variant + '-headless-windowed-' + args.tag)
    run_path, log_path = Path(str(prefix) + '-result.json'), Path(str(prefix) + '.log')
    run = json.loads(run_path.read_text())
    assert run['executableSha256'] == build['executableSha256']
    assert run['logSha256'] == sha(log_path) and run['originalDolSha256'] == sha(dol)
    assert run['recipeSha256'] == sha(Path('experiments/wii-static-recomp/run_stock_baseline.py'))
    capture = root / (variant + '-' + args.tag + '-thp-scan.jsonl')
    rows = [json.loads(line) for line in capture.read_text().splitlines()]
    assert len({row['index'] for row in rows}) == len(rows) <= 32
    results = []
    for row in rows:
        text, spec = bytes.fromhex(row['inputHex']).decode('ascii'), bytes.fromhex(row['formatHex']).decode('ascii')
        if spec == '#%x':
            assert re.fullmatch(r'#[0-9a-fA-F]+', text)
            values = [int(text[1:], 16) & 0xFFFFFFFF]
            expected = [struct.pack('>I', value).hex() for value in values]
        else:
            assert spec in ('%f:%f:%f', '%f,%f,%f,%f', '%f,%f')
            values = [float(token) for token in text.split(':' if ':' in spec else ',')]
            assert len(values) == spec.count('%f') and all(math.isfinite(value) for value in values)
            expected = [struct.pack('>f', value).hex() for value in values]
        actual = [slot['after'][:8] for slot in row['outputs'][:len(expected)]]
        results.append({'index': row['index'], 'input': text, 'format': spec, 'count': row['count'],
            'callerReturn': f'{row["lr"]:08X}', 'expected': expected, 'actual': actual,
            'passed': row['count'] == len(expected) and actual == expected})
    log = log_path.read_text(errors='replace')
    report['runtime'] = {'runSha256': sha(run_path), 'captureSha256': sha(capture),
        'terminalReturncode': run['terminalReturncode'], 'deadlineReached': run['deadlineReached'],
        'decoderCalls': len(re.findall(r'\[CALL\] 0x80209d80 ', log)), 'gpuHang': 'GPU Hang' in log,
        'statistics': re.findall(r'\[STAT\] (\d+)s frames=(\d+) draws=(\d+)', log),
        'captures': {str(path): sha(path) for path in sorted(root.glob(variant + '-' + args.tag + '-efb_*.bmp'))}}
    report['logicalComparison'] = results
    report['limits'].append('Python finite decimal-to-float32/hex logical reference, not original paired-compatible execution or caller consumption proof.')
    if not results or not all(row['passed'] for row in results):
        report['result'] = 'SCAN_CAPTURE_LOGICAL_MISMATCH'
    if args.consumption:
        consumed_path = root / (variant + '-' + args.tag + '-thp-consumed.jsonl')
        consumed = [json.loads(line) for line in consumed_path.read_text().splitlines()]
        comparisons = []
        f32 = lambda value: struct.unpack('>f', struct.pack('>f', value))[0]
        for entry in consumed:
            scan = next(row for row in rows if row['index'] == entry['index'])
            spec = bytes.fromhex(scan['formatHex']).decode('ascii')
            arguments = [slot['after'][:8] for slot in scan['outputs'][:3 if spec == '%f:%f:%f' else 4]]
            values = [struct.unpack('>f', bytes.fromhex(word))[0] for word in arguments]
            if spec == '%f:%f:%f':
                expected = struct.pack('>f', f32(values[2] + f32(f32(60 * f32(60 * values[0])) + f32(60 * values[1])))).hex()
                pc = 0x8010168C
            else:
                assert spec == '%f,%f,%f,%f'
                expected = ''.join(arguments[index] for index in (0, 2, 1, 3))
                pc = 0x8010F130
            comparisons.append({'index': entry['index'], 'expected': expected, 'actual': entry['bytes'],
                'passed': entry['pc'] == pc and entry['sp'] == scan['sp'] and entry['arguments'] == arguments and entry['bytes'] == expected})
        expected_indices = {row['index'] for row in rows if row['lr'] in (0x80101664, 0x8010F110)}
        report['unobservedConsumers'] = [{'index': row['index'], 'callerReturn': f'{row["lr"]:08X}',
            'format': bytes.fromhex(row['formatHex']).decode('ascii')}
            for row in rows if bytes.fromhex(row['formatHex']).startswith(b'%f') and row['index'] not in expected_indices]
        assert len({entry['index'] for entry in consumed}) == len(consumed)
        report['consumerComparison'] = comparisons
        report['runtime']['consumerCaptureSha256'] = sha(consumed_path)
        report['limits'].append('Consumer byte comparison covers captured finite values only; not original floating/IRQ/transition acceptance.')
        if {entry['index'] for entry in consumed} != expected_indices or not all(row['passed'] for row in comparisons):
            report['result'] = 'SCAN_CONSUMER_LOGICAL_MISMATCH'
(output / ('audit-' + (args.tag or 'component') + '.json')).write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], report.get('logicalComparison', 'component only'))
assert report['result'] == 'READ_ONLY_SCAN_OBSERVER_AUDIT_PASS'

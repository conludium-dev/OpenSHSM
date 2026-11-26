"""Check unchanged scan results on the consumer-observed linked runtime."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--numeric-reader', action='store_true')
parser.add_argument('--flight', action='store_true')
args = parser.parse_args()
assert not args.flight or args.numeric_reader
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base = root / 'window-scan-routes'
output = root / ('window-numeric-flight' if args.flight else 'window-numeric-reader' if args.numeric_reader else 'window-scan-consume')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
probe = json.loads((output / 'probe-build.json').read_text())
assert probe['parentBuildSha256'] == sha(output / 'build.json')
assert probe['executableSha256'] == sha(output / 'scan-probe')
for path, digest in probe['linkInputs'].items():
    assert sha(Path(path)) == digest
proof = json.loads((base / 'original-compare.json').read_text())
assert proof['nativeLogSha256'] == sha(base / 'original-compare-native.log')
cases = proof['cases']
request = ''.join((row['input'] or '-') + ' ' + row['format'] + '\n' for row in cases)
capture = output / 'component-scan.jsonl'
assert not capture.exists()
env = {key: value for key, value in os.environ.items() if not key.startswith(('SHSM_', 'NWII_'))}
env['NWII_THPDUMP'] = str(output / 'component')
result = subprocess.run([str(output / 'scan-probe'), str(Path('work/private-game/disc/DATA/sys/main.dol').resolve())],
    input=request, capture_output=True, text=True, env=env, timeout=120)
(output / 'component.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
native = re.findall(r'^SCAN (\d+) ([0-9a-f]{256})$', result.stdout, re.M)
reference = re.findall(r'^SCAN (\d+) ([0-9a-f]{256})$', (base / 'original-compare-native.log').read_text(), re.M)
assert native == reference and len(native) == 20
assert result.stdout.count('SCAN_ROUTES 76\n') == 1 and '[Interp]' not in result.stdout + result.stderr
records = [json.loads(line) for line in capture.read_text().splitlines()]
assert len(records) == 20
if args.flight:
    flight = json.loads((output / 'component-numeric-flight.json').read_text())
    assert flight == {'started': 8, 'finished': 8, 'overwrittenActive': 0, 'pending': []}
for index, (row, case, (count, memory)) in enumerate(zip(records, cases, native)):
    assert row['index'] == index and row['inputHex'] == case['input'] and row['formatHex'] == case['format']
    assert row['count'] == int(count) and row['sp'] == 0x80700000 and row['lr'] == 0x807F0000
    for pointer, snapshot in enumerate(row['outputs']):
        assert snapshot['before'] == 'cd' * 8 and snapshot['after'] == memory[pointer * 32:pointer * 32 + 16]
report = {'result': 'READ_ONLY_SCAN_OBSERVER_COMPONENT_PASS', 'cases': 20,
    'buildSha256': sha(output / 'build.json'), 'probeBuildSha256': sha(output / 'probe-build.json'),
    'captureSha256': sha(capture), 'logSha256': sha(output / 'component.log'), 'scriptSha256': sha(Path(__file__)),
    'limits': ['Scan output/observer equivalence only; consumer hooks are not executed by a direct scan probe.',
        'Original finite float execution oracle remains unavailable; full guest state/IRQ equivalence unverified.']}
(output / 'component.json').write_text(json.dumps(report, indent=2) + '\n')
print('SCAN_CONSUMER_RUNTIME_REGRESSION_PASS', 20, 'consumer execution not covered')

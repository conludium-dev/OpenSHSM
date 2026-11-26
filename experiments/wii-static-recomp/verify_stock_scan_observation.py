"""Compare observed native output with the established scan component and validate snapshots."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base, output = root / 'window-scan-routes', root / 'window-scan-observe'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
probe = json.loads((output / 'probe-build.json').read_text())
assert probe['parentBuildSha256'] == sha(output / 'build.json')
assert probe['executableSha256'] == sha(output / 'scan-probe')
assert build['headerSha256'] == sha(Path('experiments/wii-static-recomp/stock_scan_observation.h'))
for path, digest in probe['linkInputs'].items():
    assert sha(Path(path)) == digest
proof = json.loads((base / 'original-compare.json').read_text())
assert proof['nativeLogSha256'] == sha(base / 'original-compare-native.log')
cases = proof['cases']
request = ''.join((row['input'] or '-') + ' ' + row['format'] + '\n' for row in cases)
prefix = output / 'component'
capture = Path(str(prefix) + '-scan.jsonl')
assert not capture.exists(), 'Use existing evidence rather than overwriting a completed component capture.'
env = {key: value for key, value in os.environ.items() if not key.startswith(('SHSM_', 'NWII_'))}
env['NWII_THPDUMP'] = str(prefix)
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
for index, (row, case, (count, memory)) in enumerate(zip(records, cases, native)):
    assert row['index'] == index and row['inputHex'] == case['input'] and row['formatHex'] == case['format']
    assert row['count'] == int(count) and row['sp'] == 0x80700000 and row['lr'] == 0x807F0000
    for pointer, snapshot in enumerate(row['outputs']):
        assert snapshot['address'] == 0x80600400 + pointer * 16
        assert snapshot['before'] == 'cd' * 8
        assert snapshot['after'] == memory[pointer * 32:pointer * 32 + 16]
report = {'result': 'READ_ONLY_SCAN_OBSERVER_COMPONENT_PASS', 'cases': 20, 'outputAndCanariesEqual': True,
    'buildSha256': sha(output / 'build.json'), 'probeBuildSha256': sha(output / 'probe-build.json'),
    'referenceProofSha256': sha(base / 'original-compare.json'), 'captureSha256': sha(capture),
    'logSha256': sha(output / 'component.log'), 'scriptSha256': sha(Path(__file__)),
    'limits': ['Native equivalence to existing component, not additional original floating oracle.',
        'Probe covers string/count/output/SP/return integrity; not a complete IRQ/thread-state observation contract.']}
(output / 'component.json').write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], 20)

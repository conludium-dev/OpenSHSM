"""Verify and measure a pure select-based lookup over the actual authoritative route table."""
from pathlib import Path
import hashlib
import json
import re
import statistics
import struct
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
route_path = root / 'window-dispatch-o2/build.json'
route = json.loads(route_path.read_text())
current_path = root / 'window-vi-busy-latch/build.json'
current = json.loads(current_path.read_text())
original = Path(route['helperObjectPath'])
assert sha(original) == route['helperObjectSha256']
assert str(original) in current['linkCommand'] and current['retainedInputs'][str(original)] == sha(original)
cache = Path(tempfile.mkdtemp(prefix='openshsm-dispatch-select-', dir='/private/tmp'))
addresses = [row[0] for row in route['routeRecords']]
assert all(a <= b for a, b in zip(addresses, addresses[1:]))
table = cache / 'addresses.bin'
table.write_bytes(b''.join(struct.pack('<I', address) for address in addresses))
source = public / 'stock_dispatch_select.cpp'
probe = public / 'stock_dispatch_select_probe.cpp'
flags = ['-isysroot', '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk', '-std=c++20', '-O2', '-UNDEBUG']
obj, exe = cache / 'select.cpp.o', cache / 'select-probe'
commands = [
    ['/Library/Developer/CommandLineTools/usr/bin/c++', *flags, '-c', str(source), '-o', str(obj)],
    ['/Library/Developer/CommandLineTools/usr/bin/c++', *flags, str(probe), str(original), str(obj), '-o', str(exe)]]
for command in commands:
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert compiled.returncode == 0, compiled.stderr[-3000:]
live_path = Path('/private/tmp/openshsm-run-8gjgtj_g/headless-sc-pc-headless-windowed-vi-busy-latch.log')
live_result = json.loads(live_path.with_name(live_path.stem + '-result.json').read_text())
assert sha(live_path) == live_result['logSha256']
sampled = [int(value, 16) for value in re.findall(r'\[Sample\] pc=0x([0-9a-fA-F]+)', live_path.read_text())]
assert sampled
sample_table = cache / 'sampled-addresses.bin'
sample_table.write_bytes(b''.join(struct.pack('<I', address) for address in sampled))
run = subprocess.run([str(exe), str(table), str(sample_table)], capture_output=True, text=True, timeout=30)
assert run.returncode == 0 and 'SELECT_ROUTE_PARTITIONS_EQUAL' in run.stdout, run.stdout + run.stderr
rows = [dict(zip(['pattern', 'run', 'candidate', 'ns', 'queries', 'checksum'], map(int, values))) for values in re.findall(
    r'BATCH pattern=(\d+) run=(\d+) candidate=(\d+) ns=(\d+) queries=(\d+) checksum=(\d+)', run.stdout)]
assert len(rows) == 20
for pattern in range(2):
    assert len({row['checksum'] for row in rows if row['pattern'] == pattern}) == 1
medians = {label: {name: statistics.median(row['ns'] / row['queries'] for row in rows
    if row['candidate'] == value and row['pattern'] == pattern)
    for name, value in [('baseline', 0), ('candidate', 1)]}
    for pattern, label in [(0, 'mixedKeysGaps'), (1, 'repeatedLiveSamples')]}
output = root / 'dispatch-select-proof'
output.mkdir(exist_ok=True)
(output / 'verification.json').write_text(json.dumps({
    'result': 'SELECT_LOOKUP_ACTUAL_TABLE_PARTITIONS_AND_COARSE_BATCHES_VERIFIED',
    'currentBuildSha256': sha(current_path), 'routeBuildSha256': sha(route_path),
    'sourceSha256': sha(source), 'probeSha256': sha(probe), 'verifierSha256': sha(Path(__file__)),
    'tableSha256': sha(table), 'baselineObjectSha256': sha(original), 'candidateObjectSha256': sha(obj),
    'executableSha256': sha(exe), 'commands': commands, 'stdout': run.stdout, 'rows': rows, 'medianNs': medians,
    'sampledLiveLogSha256': sha(live_path), 'sampledLiveAddresses': len(sampled),
    'limits': ['Pure helper experiment over same actual table, no second runtime table/cache and no game source/link edits.',
        'All key/gap boundary/midpoint representatives and duplicate/empty/extreme inputs compared with standard lower_bound.',
        'Synthetic mixed key/gap coarse batches include call/loop overhead, not actual decoder-exclusive CPU/FPS proof.',
        'Repeated actual live sampled PCs are a sparse time-biased sequence, not complete dispatch call-frequency trace.',
        'Native callbacks/frames/live cadence verification needed before integration.']}, indent=2) + '\n')
print('SELECT_LOOKUP_ACTUAL_TABLE_PARTITIONS_AND_COARSE_BATCHES_VERIFIED', medians)

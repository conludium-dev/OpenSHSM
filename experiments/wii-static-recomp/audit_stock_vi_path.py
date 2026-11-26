"""Verify alias-complete VI observations; a bounded run is not boot acceptance."""
import argparse
import collections
import hashlib
import json
import re
import struct
from pathlib import Path
from stock_vi_path_observation import adapt_vi_path

parser = argparse.ArgumentParser()
parser.add_argument('--tag', required=True)
args = parser.parse_args()
assert re.fullmatch(r'[a-z0-9-]{1,40}', args.tag)
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-vi-path'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
base = root / 'window-optimized/output_39.cpp'
text, stages, calls = adapt_vi_path(base.read_text())
assert text == (output / 'output_39.cpp').read_text()
assert sha(base) == build['baseSourceSha256'] and sha(output / 'output_39.cpp') == build['sourceSha256']
opcodes = lambda source: re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', source)
assert opcodes(text) == opcodes(base.read_text())
assert len(build['retainedObjects']) == 76
assert all(sha(Path(name)) == expected for name, expected in build['retainedObjects'].items())
assert sha(root / 'window-draw-done/libnwiiruntime.a') == build['archiveSha256']
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
header = struct.unpack('>64I', dol[:256])

def word(address):
    section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
    return struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0]

table = [word(0x8043BD08 + i * 4) for i in range(5)]
assert table == [0x80228440, 0x80228448, 0x80228450, 0x80228440, 0x80228448]
for address, opcode in opcodes(text):
    if 0x802280F0 <= int(address, 16) < 0x80228900:
        assert word(int(address, 16)) == int(opcode, 16)
label = 'window-vi-path-headless-gx-windowed-' + args.tag
run = json.loads((root / (label + '-result.json')).read_text())
assert run['executableSha256'] == sha(output / 'OpenSHSMStockVIPath') == build['executableSha256']
assert run['logSha256'] == sha(root / (label + '.log'))
log = (root / (label + '.log')).read_text(errors='replace')
pattern = r'\[VIPath\] ns=(\d+) stage=([0-9a-f]+) yield=(\d) pc=([0-9a-f]+) lr=([0-9a-f]+) r1=([0-9a-f]+) r0=([0-9a-f]+) r3=([0-9a-f]+) r4=([0-9a-f]+) ctr=([0-9a-f]+) r13=([0-9a-f]+) r31=([0-9a-f]+) msr=([0-9a-f]+) token=([0-9a-f]+) vi=([0-9a-f:]+) flags=([0-9a-f:]+)'
rows = re.findall(pattern, log)
assert rows, 'No complete VI observations; coverage not proven'
counts = collections.Counter(row[1] + ':' + row[2] for row in rows)
post_targets = collections.Counter(row[9] for row in rows if row[1] == '80228630' and row[2] == '0')
report = {
    'result': 'READ_ONLY_VI_SOURCE_AND_RUN_PROVENANCE_PASS',
    'dolSha256': sha(dol_path), 'jumpTable': table, 'completeRecords': len(rows),
    'sampledStageCounts': dict(counts), 'postRetraceTargets': dict(post_targets),
    'maxObservedToken': max(int(row[13], 16) for row in rows),
    'terminalReturncode': run['terminalReturncode'], 'gpuHangReported': 'GPU Hang' in log,
    'retainedObjects': 76, 'observedCallReturnChecks': calls,
    'buildSha256': sha(output / 'build.json'), 'runSha256': sha(root / (label + '-result.json')),
    'limits': ['Sampled observations can omit executions; missing marker alone is not missing callback proof.',
        'Diagnostic timings differ; no full boot/menu/gameplay or original dynamic Wii acceptance.',
        'Watchdog wrapper must be distinguished from the saved post-retrace callback.']
}
(output / ('audit-' + args.tag + '.json')).write_text(json.dumps(report, indent=2) + '\n')
print('PASS alias-complete VI source/run audit;', len(rows), 'records; post targets', dict(post_targets))

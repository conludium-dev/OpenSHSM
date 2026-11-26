"""Audit read-only movie queue samples and group before-call occupancy, not completed receives."""
from pathlib import Path
import argparse
from collections import defaultdict, Counter
import hashlib
import json
import re
import subprocess
import struct

parser = argparse.ArgumentParser()
parser.add_argument('--tag', required=True)
args = parser.parse_args()
assert re.fullmatch('[a-z0-9-]{1,40}', args.tag)
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base, output = root / 'interpreter-addze-corrected', root / 'window-movie-queues'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert build['baseBuildSha256'] == sha(base / 'build.json')
original = root / 'window-quantization/os_hle_stubs.cpp'
assert sha(original) == build['originalSourceSha256']
marker = '  if (!g_trace_only.empty() && !g_trace_only.count(func_addr)) return;'
expected = '#include "stock_thp_queue_observation.h"\n' + original.read_text().replace(marker,
    marker + '\n  stock_thp_queue_observation::observe(ctx, func_addr);')
assert (output / 'os_hle_stubs.cpp').read_text() == expected
for name, field in [('os_hle_stubs.cpp', 'sourceSha256'), ('os_hle_stubs.cpp.o', 'objectSha256'),
    ('libnwiiruntime.a', 'archiveSha256'), ('OpenSHSMStockMovieQueues', 'executableSha256')]:
    assert sha(output / name) == build[field]
assert sha(Path('experiments/wii-static-recomp/stock_thp_queue_observation.h')) == build['headerSha256']
assert sha(Path('experiments/wii-static-recomp/stock_loading_observation.h')) == build['copyHelperSha256']
for path, digest in build['retainedInputs'].items():
    assert sha(Path(path)) == digest
for member, digest in build['retainedMembers'].items():
    data = subprocess.check_output(['/usr/bin/ar', '-p', str(output / 'libnwiiruntime.a'), member])
    assert hashlib.sha256(data).hexdigest() == digest
component = json.loads((output / 'component.json').read_text())
assert component['result'] == 'MOVIE_QUEUE_HELPER_COMPONENT_PASS' and component['events'] == 2
assert component['buildSha256'] == sha(output / 'build.json')
for name, field in [('observer-contract', 'executableSha256'), ('contract.cpp.o', 'objectSha256'),
    ('component-movie-queues.jsonl', 'captureSha256'), ('contract.log', 'logSha256')]:
    assert sha(output / name) == component[field]
assert sha(Path('experiments/wii-static-recomp/stock_thp_queue_contract.cpp')) == component['sourceSha256']
label = 'window-movie-queues-headless-windowed-' + args.tag
run_path, log_path = root / (label + '-result.json'), root / (label + '.log')
run = json.loads(run_path.read_text())
assert run['executableSha256'] == build['executableSha256'] and run['logSha256'] == sha(log_path)
assert run['recipeSha256'] == sha(Path('experiments/wii-static-recomp/run_stock_baseline.py'))
assert run['originalDolSha256'] == sha(Path('work/private-game/disc/DATA/sys/main.dol'))
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
header = struct.unpack('>64I', dol[:256])
source_facts = []
for address, expected in [(0x80217DA0, 0x80BC0010), (0x80217D8C, 0x80DC0014),
    (0x80217D98, 0x801C0018), (0x80217D88, 0x809C001C), (0x80217E70, 0x807F0010),
    (0x80217E7C, 0x901C0000), (0x802AE504, 0x386DCB68), (0x802AE508, 0x4BF6CFD9),
    (0x8009C6B0, 0x3865E7E8), (0x8009C6B8, 0x4817B678),
    (0x8009B760, 0x4817C5D1), (0x8009B76C, 0x938300F8), (0x8009BA6C, 0x48000C3D)]:
    section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
    opcode = struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0]
    assert opcode == expected
    source_facts.append({'address': f'{address:08X}', 'opcode': f'{opcode:08X}'})
capture = root / ('window-movie-queues-' + args.tag + '-thp-movie-queues.jsonl')
rows = [json.loads(line) for line in capture.read_text().splitlines()] if capture.exists() else []
groups = defaultdict(list)
for index, row in enumerate(rows):
    assert row['serial'] == index and 0x80090000 <= row['caller'] < 0x800A0000
    assert row['function'] in (0x80217D30, 0x80217E00)
    if row['fieldsValid']:
        words = [int(row['queueHex'][i:i + 8], 16) for i in range(0, 64, 8)]
        assert (row['capacity'], row['first'], row['count']) == tuple(words[5:8])
    groups[(row['function'], row['queue'], row['caller'])].append(row)
summary = [{'function': f'{key[0]:08X}', 'queue': f'{key[1]:08X}', 'caller': f'{key[2]:08X}',
    'samples': len(items), 'observedHits': items[-1]['hits'],
    'occupancies': dict(Counter(row['count'] for row in items)),
    'messages': sorted({f'{row["argument4"]:08X}' for row in items}) if key[0] == 0x80217D30 else [],
    'last': items[-1]} for key, items in groups.items()]
log = log_path.read_text(errors='replace')
report = {'result': 'MOVIE_QUEUE_OBSERVER_PROVENANCE_AUDIT_PASS', 'events': len(rows),
    'coverage': 'OBSERVED' if rows else 'NOT_REACHED', 'dolInstructionFacts': source_facts,
    'eventCapReached': len(rows) == 20000, 'groups': summary,
    'buildSha256': sha(output / 'build.json'), 'componentSha256': sha(output / 'component.json'),
    'runSha256': sha(run_path), 'captureSha256': sha(capture) if capture.exists() else None,
    'terminalReturncode': run['terminalReturncode'], 'deadlineReached': run['deadlineReached'],
    'decoderCalls': len(re.findall(r'\[CALL\] 0x80209d80 ', log)),
    'statistics': re.findall(r'\[STAT\] (\d+)s frames=(\d+) draws=(\d+)', log),
    'captures': {str(path): sha(path) for path in root.glob('window-movie-queues-' + args.tag + '-efb_*.bmp')},
    'limits': build['limits'] + component['limits']}
(output / ('audit-' + args.tag + '.json')).write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], 'events', len(rows), 'groups', len(groups))
print(json.dumps([{key: group[key] for key in ('function', 'queue', 'caller', 'samples', 'observedHits', 'occupancies')}
    for group in summary], indent=2))

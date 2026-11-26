"""Verify read-only observer provenance and summarize actual numeric/context coverage."""
from pathlib import Path
import argparse
import collections
import hashlib
import json
import re
import subprocess
from stock_numeric_observation import adapt_calls, adapt_contexts
from stock_thp_observation import adapt_thp_calls

parser = argparse.ArgumentParser()
parser.add_argument('--tag')
parser.add_argument('--thp', action='store_true')
args = parser.parse_args()
assert args.tag is None or re.fullmatch(r'[a-z0-9-]{1,40}', args.tag)
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base = root / 'window-locked-cache'
variant = 'window-lc-thp' if args.thp else 'window-lc-numeric'
output = root / variant
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert sha(base / 'build.json') == build['baseBuildSha256']
adapters = [('os_hle_stubs.cpp', adapt_thp_calls)] if args.thp else [('os_hle_stubs.cpp', adapt_calls), ('ios.cpp', adapt_contexts)]
for name, adapter in adapters:
    assert (output / name).read_text() == adapter((base / name).read_text())
    assert sha(output / name) == build['sources'][name]['sourceSha256']
    assert sha(output / (name + '.o')) == build['sources'][name]['objectSha256']
assert len(build['retainedObjects']) == 77
assert len(build['retainedRuntimeMembers']) == (44 if args.thp else 43)
assert all(sha(Path(name)) == expected for name, expected in build['retainedObjects'].items())
for member, expected in build['retainedRuntimeMembers'].items():
    for archive in (base / 'libnwiiruntime.a', output / 'libnwiiruntime.a'):
        assert hashlib.sha256(subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])).hexdigest() == expected
assert sha(output / 'libnwiiruntime.a') == build['archiveSha256']
assert sha(output / ('OpenSHSMStockTHPObserver' if args.thp else 'OpenSHSMStockNumericObserver')) == build['executableSha256']
report = {'result': 'READ_ONLY_THP_OBSERVER_PROVENANCE_PASS' if args.thp else 'READ_ONLY_NUMERIC_OBSERVER_PROVENANCE_PASS', 'limits': build['limits']}
if args.tag:
    prefix = root / (variant + '-headless-windowed-' + args.tag)
    run_path, log_path = Path(str(prefix) + '-result.json'), Path(str(prefix) + '.log')
    run = json.loads(run_path.read_text())
    assert run['executableSha256'] == build['executableSha256'] and run['logSha256'] == sha(log_path)
    assert run['originalDolSha256'] == sha(Path('work/private-game/disc/DATA/sys/main.dol'))
    pattern = r'\[NumericState\] event=(call|save|load) hit=(\d+) subject=([0-9a-f]+) pc=([0-9a-f]+) lr=([0-9a-f]+) ctr=([0-9a-f]+) xer=([0-9a-f]+) msr=([0-9a-f]+) cr=([0-9a-f]+) gpr=((?:[0-9a-f]+,){32}) mem3=([0-9a-f]{128}|-) mem4=([0-9a-f]{128}|-) mem5=([0-9a-f]{128}|-)'
    log = log_path.read_text(errors='replace')
    records = []
    for row in re.findall(pattern, log):
        records.append({'event': row[0], 'hit': int(row[1]),
            **{name: int(value, 16) for name, value in zip(('subject', 'pc', 'lr', 'ctr', 'xer', 'msr', 'cr'), row[2:9])},
            'gpr': [int(value, 16) for value in row[9].split(',')[:-1]],
            'memory': [row[10], row[11], row[12]]})
    report.update({'runSha256': sha(run_path), 'terminalReturncode': run['terminalReturncode'],
        'deadlineReached': run['deadlineReached'], 'counts': dict(collections.Counter(row['event'] for row in records)),
        'records': records, 'gpuHangReported': 'GPU Hang' in log,
        'decoderCalls': len(re.findall(r'\[CALL\] 0x80209d80 ', log)),
        'dmaCommandCalls': len(re.findall(r'\[CALL\] 0x80213240 ', log))})
    if args.thp:
        captures = sorted(root.glob(variant + '-' + args.tag + '-thp-*.bin'))
        report.update(packetRecords=re.findall(r'\[THPInput\] index=(\d+) address=([0-9a-f]+) bytes=(\d+)', log),
            planeRecords=re.findall(r'\[THPPlanes\] frame=(\d+) y=([0-9a-f]+) u=([0-9a-f]+) v=([0-9a-f]+) width=640 height=480', log),
            captures={path.name: {'bytes': path.stat().st_size, 'sha256': sha(path)} for path in captures})
(output / ('audit-' + (args.tag or 'component') + '.json')).write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], report.get('counts', 'run unverified'), 'decoder=', report.get('decoderCalls'))

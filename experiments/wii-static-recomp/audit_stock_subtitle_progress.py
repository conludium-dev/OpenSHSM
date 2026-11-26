"""Audit original subtitle checkpoints and summarize actual cursor/time-conversion progress."""
from pathlib import Path
import argparse
import collections
import hashlib
import json
import re
import struct
from stock_subtitle_progress import adapt

parser = argparse.ArgumentParser()
parser.add_argument('--tag')
args = parser.parse_args()
assert args.tag is None or re.fullmatch('[a-z0-9-]{1,40}', args.tag)
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base, output = root / 'window-loading-payload', root / 'window-subtitle-progress'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert build['baseBuildSha256'] == sha(base / 'build.json')
parent = json.loads((base / 'build.json').read_text())
assert parent['headerSha256'] == sha(Path('experiments/wii-static-recomp/stock_loading_observation.h'))
original = Path(build['originalPath'])
assert sha(original) == build['originalSha256']
dol = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
assert (output / 'output_16.cpp').read_text() == adapt(original.read_text(), dol.read_bytes())
assert sha(output / 'output_16.cpp') == build['sourceSha256'] and sha(output / 'output_16.cpp.o') == build['objectSha256']
assert sha(Path('experiments/wii-static-recomp/stock_subtitle_progress.h')) == build['headerSha256']
assert sha(output / 'OpenSHSMStockSubtitleProgress') == build['executableSha256']
for path, digest in build['retainedInputs'].items():
    assert sha(Path(path)) == digest
component = json.loads((output / 'component.json').read_text())
assert component['result'] == 'SUBTITLE_PROGRESS_HELPER_COMPONENT_PASS'
assert component['buildSha256'] == sha(output / 'build.json')
assert component['headerSha256'] == build['headerSha256']
assert component['sourceSha256'] == sha(Path('experiments/wii-static-recomp/stock_subtitle_progress_contract.cpp'))
assert component['baseContractSha256'] == sha(Path('experiments/wii-static-recomp/stock_loading_observation_contract.cpp'))
assert component['objectSha256'] == sha(output / 'contract.cpp.o')
assert component['executableSha256'] == sha(output / 'observer-contract')
assert component['captureSha256'] == sha(output / 'component-subtitle-progress.jsonl')
for path, digest in component['linkInputs'].items():
    assert sha(Path(path)) == digest
report = {'result': 'READ_ONLY_SUBTITLE_PROGRESS_AUDIT_PASS', 'componentEvents': 6,
    'limits': build['limits'] + component['limits']}
if args.tag:
    prefix = root / ('window-subtitle-progress-headless-windowed-' + args.tag)
    run_path, log_path = Path(str(prefix) + '-result.json'), Path(str(prefix) + '.log')
    run = json.loads(run_path.read_text())
    assert run['executableSha256'] == build['executableSha256'] and run['logSha256'] == sha(log_path)
    assert run['originalDolSha256'] == sha(dol) and run['recipeSha256'] == sha(Path('experiments/wii-static-recomp/run_stock_baseline.py'))
    capture = root / ('window-subtitle-progress-' + args.tag + '-thp-subtitle-progress.jsonl')
    rows = [json.loads(line) for line in capture.read_text().splitlines()] if capture.exists() else []
    assert [row['serial'] for row in rows] == list(range(len(rows)))
    assert all(rows[i]['hostMs'] <= rows[i + 1]['hostMs'] for i in range(len(rows) - 1))
    starts, finished, pending = {}, [], {}
    for row in rows:
        key = (row['cues'], row['sp'], row['scriptNode'], row['cueNode'], row['cueData'])
        if row['event'] == 'time-before':
            assert key not in starts
            starts[key] = row
            pending[key] = row
        elif row['event'] == 'time-after' and key in pending:
            before = pending.pop(key)
            value = bytes.fromhex(before['inputHex']).decode('ascii')
            expected = struct.pack('>f', float(value)).hex()
            finished.append({'cue': row['cues'], 'input': value, 'hostDurationMs': row['hostMs'] - before['hostMs'],
                'expected': expected, 'actual': row['timeHex'], 'logicalMatch': expected == row['timeHex']})
    log = log_path.read_text(errors='replace')
    report['runtime'] = {'runSha256': sha(run_path), 'captureSha256': sha(capture) if capture.exists() else None,
        'terminalReturncode': run['terminalReturncode'], 'deadlineReached': run['deadlineReached'],
        'decoderCalls': len(re.findall(r'\[CALL\] 0x80209d80 ', log)), 'gpuHang': 'GPU Hang' in log,
        'statistics': re.findall(r'\[STAT\] (\d+)s frames=(\d+) draws=(\d+)', log),
        'captures': {str(path): sha(path) for path in sorted(root.glob('window-subtitle-progress-' + args.tag + '-efb_*.bmp'))}}
    report['progress'] = {'coverage': 'REACHED' if rows else 'NOT_REACHED', 'events': len(rows), 'captureCapReached': len(rows) == 32768,
        'eventCounts': dict(collections.Counter(row['event'] for row in rows)),
        'distinctScriptNodes': len({row['scriptNode'] for row in rows if row['event'] == 'script'}),
        'distinctCueNodes': len({row['cueNode'] for row in rows if row['event'] == 'cue'}),
        'timeConversionsFinished': finished, 'pendingTimes': list(pending.values()), 'lastEvent': rows[-1] if rows else None}
    report['limits'].append('Python float32 logical comparison is not original paired-compatible oracle; missing return by deadline does not prove infinite loop. Numeric text is capped80bytes.')
(output / ('audit-' + (args.tag or 'component') + '.json')).write_text(json.dumps(report, indent=2) + '\n')
print(report['result'])
if args.tag:
    print({key: report['progress'][key] for key in ('events', 'eventCounts', 'distinctScriptNodes', 'distinctCueNodes', 'pendingTimes', 'lastEvent')})

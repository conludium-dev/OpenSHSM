"""Verify scoped numeric callback observer and inspect actual state transitions."""
from pathlib import Path
import argparse
import hashlib
import json
import re
from stock_idct_callbacks import adapt_callbacks

parser = argparse.ArgumentParser()
parser.add_argument('--tag')
parser.add_argument('--nonlocal-unwind', action='store_true')
args = parser.parse_args()
assert args.tag is None or re.fullmatch(r'[a-z0-9-]{1,40}', args.tag)
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base, full, output = root / 'window-idct-callbacks', root / 'window-quantization', root / 'window-numeric-callbacks'
variant = 'window-numeric-unwind' if args.nonlocal_unwind else 'window-numeric-callbacks'
output = root / variant
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
previous = json.loads((base / 'build.json').read_text())
parent = json.loads((full / 'build.json').read_text())
assert sha(base / 'build.json') == build['baseBuildSha256']
assert sha(full / 'build.json') == build['fullBuildSha256']
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
text, sites = adapt_callbacks((full / 'output_30.cpp').read_text(), dol_path.read_bytes(), numeric=True, nonlocal_unwind=args.nonlocal_unwind)
assert text == (output / 'output_30.cpp').read_text() and sites == build['sites']
assert sha(output / 'output_30.cpp') == build['sourceSha256'] and sha(output / 'output_30.cpp.o') == build['objectSha256']
assert build['arguments'] == next(row['arguments'] for row in parent['compiled'] if row['source'] == 'output_30.cpp')
assert sha(full / 'include/runtime/cpu_context.h') == parent['cpuHeaderSha256']
assert all(sha(Path(path)) == expected for path, expected in build['retainedInputs'].items())
exe_name = 'OpenSHSMStockNumericUnwind' if args.nonlocal_unwind else 'OpenSHSMStockNumericCallbacks'
assert sha(output / exe_name) == build['executableSha256']
command = list(previous['linkCommand'])
command[command.index(str(full / 'output_30.cpp.o'))] = str(output / 'output_30.cpp.o')
command[command.index('-o') + 1] = str(output / exe_name)
assert command == build['linkCommand']
report = {'result': 'NUMERIC_CALLBACK_PROVENANCE_PASS', 'sites': len(sites), 'limits': build['limits']}
if args.tag:
    prefix = root / (variant + '-headless-windowed-' + args.tag)
    log_path, run_path = Path(str(prefix) + '.log'), Path(str(prefix) + '-result.json')
    run = json.loads(run_path.read_text())
    assert run['logSha256'] == sha(log_path) and run['executableSha256'] == build['executableSha256']
    assert run['originalDolSha256'] == sha(dol_path)
    log = log_path.read_text(errors='replace')
    records = []
    for match in re.finditer(r'\[NumericTransition\] ([^\n]+)', log):
        row = dict(re.findall(r'(\w+)=(\S*)', match[1]))
        if not all(key in row for key in ('phase', 'handled', 'pc', 'next', 'context', 'nextContext',
            'gprMask', 'fprMask', 'ps1Mask', 'ctrBefore', 'ctrAfter', 'lrBefore', 'lrAfter', 'xerBefore', 'xerAfter', 'crBefore', 'crAfter')):
            continue
        records.append(row)
    same_context = lambda row: row['context'] == row['nextContext'] and row['pc'] == row['next']
    report.update(returncode=run['terminalReturncode'], deadlineReached=run['deadlineReached'], records=records,
        coverageSamples=re.findall(r'\[NumericCoverage\] calls=(\d+) pc=([0-9a-f]+) context=([0-9a-f]+)', log),
        decoderCalls=len(re.findall(r'\[CALL\] 0x80209d80 ', log)), runSha256=sha(run_path),
        directStateDifferences=[row for row in records if row['phase'] == 'checkpoint' and row['handled'] == '0' and same_context(row)],
        candidateResumes=[row for row in records if row['phase'] == 'resume'])
(output / ('audit-' + (args.tag or 'component') + '.json')).write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], 'records=', len(report.get('records', [])), 'resumes=', len(report.get('candidateResumes', [])))
for row in report.get('directStateDifferences', [])[:4]:
    print(row)

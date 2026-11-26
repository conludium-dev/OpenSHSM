"""Bind the corrected fallback component and bounded game observation to exact artifacts."""
from pathlib import Path
import argparse
from collections import Counter
import hashlib
import json
import re
import subprocess
from stock_interpreter_carry import adapt
from stock_interpreter_addze import adapt as adapt_addze

parser = argparse.ArgumentParser()
parser.add_argument('--tag', required=True)
parser.add_argument('--addze', action='store_true')
args = parser.parse_args()
assert re.fullmatch('[a-z0-9-]{1,40}', args.tag)
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
variant = 'interpreter-addze-corrected' if args.addze else 'interpreter-carry-corrected'
output = root / variant
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
component = json.loads((output / 'comparison.json').read_text())
assert component['result'] == 'ORIGINAL_DOL_INTERPRETER_CARRY_COMPONENT_PASS'
assert component['cases'] == (588 if args.addze else 392) and component['mismatches'] == []
assert sha(Path('experiments/wii-static-recomp/verify_stock_interpreter_carry.py')) == component['verifierSha256']
assert sha(Path('experiments/wii-static-recomp/stock_interpreter_carry_probe.cpp')) == component['sourceSha256']
assert sha(output / 'probe') == component['executableSha256']
assert sha(output / 'probe.cpp.o') == component['objectSha256']
assert sha(output / 'native.log') == component['logSha256']
assert build['baseBuildSha256'] == component['baseBuildSha256'] == sha(root / 'window-numeric-flight/build.json')
original = root / 'window-scan-consume/interpreter.cpp'
assert (output / 'interpreter.cpp').read_text() == (adapt_addze if args.addze else adapt)(original.read_text())
runtime = build['runtime']
assert runtime == component['runtime']
assert sha(original) == runtime['originalSourceSha256']
assert sha(output / 'interpreter.cpp') == runtime['sourceSha256']
assert sha(output / 'interpreter.cpp.o') == runtime['objectSha256']
assert sha(output / 'libnwiiruntime.a') == runtime['archiveSha256']
assert sha(Path('experiments/wii-static-recomp/stock_interpreter_addze.py' if args.addze
    else 'experiments/wii-static-recomp/stock_interpreter_carry.py')) == runtime['adapterSha256']
if args.addze:
    assert sha(Path('experiments/wii-static-recomp/stock_interpreter_carry.py')) == runtime['carryAdapterSha256']
for path, digest in component['linkInputs'].items():
    assert sha(Path(path)) == digest
for member, digest in runtime['retainedMembers'].items():
    data = subprocess.check_output(['arch', '-arm64', '/usr/bin/ar', '-p', str(output / 'libnwiiruntime.a'), member])
    assert hashlib.sha256(data).hexdigest() == digest
exe = output / ('OpenSHSMStockInterpreterAddze' if args.addze else 'OpenSHSMStockInterpreterCarry')
assert sha(exe) == build['executableSha256']
label = variant + '-headless-windowed-' + args.tag
run_path, log_path = root / (label + '-result.json'), root / (label + '.log')
run = json.loads(run_path.read_text())
assert run['executableSha256'] == build['executableSha256']
assert run['recipeSha256'] == sha(Path('experiments/wii-static-recomp/run_stock_baseline.py'))
assert run['logSha256'] == sha(log_path)
assert run['originalDolSha256'] == component['dolSha256'] == sha(Path('work/private-game/disc/DATA/sys/main.dol'))
prefix = root / (variant + '-' + args.tag + '-thp')
captures = {}
def read_rows(suffix):
    path = Path(str(prefix) + suffix)
    if not path.exists():
        return []
    captures[str(path)] = sha(path)
    return [json.loads(line) for line in path.read_text().splitlines()]
loading = read_rows('-loading.jsonl')
subtitles = read_rows('-subtitle-progress.jsonl')
summary_path = Path(str(prefix) + '-numeric-flight.json')
assert summary_path.exists(), 'Missing shutdown summary is not proof of completion'
summary = json.loads(summary_path.read_text())
captures[str(summary_path)] = sha(summary_path)
for row in summary['pending']:
    row['input'] = bytes.fromhex(row['inputHex']).decode('ascii')
    row['callerHex'] = f'{row["caller"]:08X}'
log = log_path.read_text(errors='replace')
report = {'result': 'CORRECTED_INTERPRETER_CARRY_PROVENANCE_AUDIT_PASS',
    'componentCases': component['cases'], 'retainedRuntimeObjects': len(runtime['retainedMembers']),
    'buildSha256': sha(output / 'build.json'), 'componentSha256': sha(output / 'comparison.json'),
    'runSha256': sha(run_path), 'captures': captures, 'terminalReturncode': run['terminalReturncode'],
    'deadlineReached': run['deadlineReached'], 'numericFlight': summary,
    'loadingEventCounts': dict(Counter(row['event'] for row in loading)),
    'lastLoadingEvents': loading[-5:], 'subtitleEventCounts': dict(Counter(row['event'] for row in subtitles)),
    'distinctScriptNodes': len({row['scriptNode'] for row in subtitles if row['event'] == 'script'}),
    'distinctCueNodes': len({row['cueNode'] for row in subtitles if row['event'] == 'cue'}),
    'subtitleObservedHostSpanMs': subtitles[-1]['hostMs'] - subtitles[0]['hostMs'] if subtitles else None,
    'lastSubtitleEvents': subtitles[-5:],
    'statistics': re.findall(r'\[STAT\] (\d+)s frames=(\d+) draws=(\d+)', log),
    'decoderCalls': len(re.findall(r'\[CALL\] 0x80209d80 ', log)),
    'thpPlanePublications': re.findall(r'\[THPPlanes\] [^\n]+', log),
    'thpCapturedFiles': {str(path): sha(path) for path in root.glob(variant + '-' + args.tag + '-thp-*.bin')},
    'unhandledCarryInstructions': re.findall(r'\[Interp\] Unhandled op31 xo=(?:10|138|202) at [^\n]+', log),
    'allUnhandledInstructions': dict(Counter(re.findall(r'\[Interp\] Unhandled ([^\n]+)', log))),
    'efbCaptures': {str(path): sha(path) for path in root.glob(variant + '-' + args.tag + '-efb_*.bmp')},
    'limits': ['Artifact and bounded observation audit, not full original behavior or rendered menu acceptance.',
        'No subtitle checkpoint or no paired return is coverage evidence, not permanent-loop proof.']}
regression_path = output / 'scan-regression.json'
if regression_path.exists():
    regression = json.loads(regression_path.read_text())
    assert regression['buildSha256'] == sha(output / 'build.json')
    assert regression['scriptSha256'] == sha(Path('experiments/wii-static-recomp/verify_stock_interpreter_carry_scan.py'))
    assert regression['logSha256'] == sha(output / 'scan-regression.log')
    assert regression['executableSha256'] == sha(output / 'scan-probe')
    for path, digest in regression['linkInputs'].items():
        assert sha(Path(path)) == digest
    report['scanRegressionSha256'] = sha(regression_path)
    report['scanRegressionCases'] = regression['regressionCases']
(output / ('audit-' + args.tag + '.json')).write_text(json.dumps(report, indent=2) + '\n')
print(report['result'])
print(json.dumps({key: report[key] for key in ('numericFlight', 'loadingEventCounts', 'subtitleEventCounts',
    'decoderCalls', 'unhandledCarryInstructions', 'allUnhandledInstructions')}, indent=2))

"""Audit every guarded module and unchanged dependency before allowing a boot probe."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
from stock_fp_guard_lowering import lower
from stock_fp_unavailable_patch import adapt_interpreter
from stock_ring_observation import summarize

parser = argparse.ArgumentParser()
parser.add_argument('--tag')
parser.add_argument('--loop-observation', action='store_true')
args = parser.parse_args()
assert args.tag is None or re.fullmatch(r'[a-z0-9-]{1,40}', args.tag)

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base, full, output = root / 'window-fp-lazy-context', root / 'window-quantization', root / 'window-fp-guard'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert sha(base / 'build.json') == build['baseBuildSha256']
assert sha(full / 'build.json') == build['fullBuildSha256']
reference = json.loads((root / 'fp-guard-component/report.json').read_text())
for item in reference['inputs']:
    assert sha(Path(item['path'])) == item['sha256']
dol_path = Path('work/private-game/disc/DATA/sys/main.dol').resolve()
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
expected_command = list(json.loads((base / 'build.json').read_text())['linkCommand'])
assert len(build['compiled']) == 75
for row in build['compiled']:
    if not row['sites']:
        assert sha(Path(row['retainedPath'])) == row['retainedSha256']
        continue
    original = Path(row['baseSourcePath'])
    assert sha(original) == row['baseSourceSha256']
    text, sites, fpscr = lower(original.read_text(), dol, reference['tables'])
    assert sites == row['sites'] and fpscr == row['fpscrLowerings']
    assert (output / row['source']).read_text() == text
    assert sha(output / row['source']) == row['sourceSha256']
    assert sha(Path(row['object'])) == row['objectSha256']
    for path, digest in row['dependencies'].items():
        assert sha(Path(path)) == digest
    matches = [i for i, path in enumerate(expected_command) if path.endswith('/' + row['source'] + '.o')]
    assert len(matches) == 1
    expected_command[matches[0]] = row['object']
expected_command[expected_command.index(str(base / 'libnwiiruntime.a'))] = str(output / 'libnwiiruntime.a')
expected_command[expected_command.index('-o') + 1] = str(output / 'OpenSHSMStockFPGuard')
assert expected_command == build['linkCommand']
text = adapt_interpreter((full / 'interpreter.cpp').read_text(), complete=True)
text = text.replace('#include "stock_fp_unavailable.h"\n', '#include "stock_fp_unavailable.h"\n#include "fpscr_adapter.h"\n')
text = text.replace('case 38: case 70: case 134: case 711: break;',
    'case 711: experiment_mtfsf(ctx, insn); break;\n        case 38: case 70: case 134: break;')
assert (output / 'interpreter.cpp').read_text() == text
assert sha(output / 'interpreter.cpp') == build['interpreterSourceSha256']
assert sha(output / 'interpreter.cpp.o') == build['interpreterObjectSha256']
assert sha(output / 'libnwiiruntime.a') == build['archiveSha256']
assert sha(output / 'OpenSHSMStockFPGuard') == build['executableSha256']
assert subprocess.check_output(['/usr/bin/ar', '-p', str(output / 'libnwiiruntime.a'), 'interpreter.cpp.o']) == (output / 'interpreter.cpp.o').read_bytes()
assert len(build['retainedRuntimeMembers']) == 44
for member, digest in build['retainedRuntimeMembers'].items():
    for archive in (base / 'libnwiiruntime.a', output / 'libnwiiruntime.a'):
        assert hashlib.sha256(subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])).hexdigest() == digest
for path, digest in build['dependencies'].items():
    assert sha(Path(path)) == digest
component = root / 'fp-exception-nonlocal-component'
contract = json.loads((component / 'report.json').read_text())
assert contract['nonlocalTransfer'] and contract['lazyContext']
for item in contract['inputs']:
    assert sha(Path(item['path'])) == item['sha256']
result = subprocess.run([str(component / 'fp-exception-contract'), str(dol_path)], capture_output=True, text=True, timeout=20)
assert result.returncode == 0 and not result.stderr and result.stdout.strip() == contract['output']
guard_test = subprocess.run([str(root / 'fp-guard-component/fp-guard-contract')], capture_output=True, text=True, timeout=20)
assert guard_test.returncode == 0 and guard_test.stdout.strip() == reference['output']
assert build['guardCount'] == sum(len(row['sites']) for row in build['compiled'])
report = {'result': 'FP_GUARDS_INTEGRATION_PROVENANCE_COMPONENT_PASS_BOOT_UNVERIFIED',
    'guardCount': build['guardCount'], 'changedModules': sum(bool(row['sites']) for row in build['compiled']),
    'classification': guard_test.stdout.strip(), 'sdk': result.stdout.strip(),
    'limits': build['limits'] + contract['limits'] + reference['limits']}
if args.tag:
    prefix = root / ('window-fp-guard-' + ('trace' if args.loop_observation else 'headless') + '-windowed-' + args.tag)
    run_path, log_path = Path(str(prefix) + '-result.json'), Path(str(prefix) + '.log')
    run = json.loads(run_path.read_text())
    assert run['executableSha256'] == build['executableSha256'] and run['logSha256'] == sha(log_path)
    assert run['originalDolSha256'] == sha(dol_path)
    log = log_path.read_text(errors='replace')
    report['runtime'] = {'terminalReturncode': run['terminalReturncode'], 'deadlineReached': run['deadlineReached'],
        'runSha256': sha(run_path), 'decoderCalls': len(re.findall(r'\[CALL\] 0x80209d80 ', log)),
        'fpuHandlerCalls': len(re.findall(r'\[CALL\] 0x80213dc0 ', log)),
        'fpuHandlerTraceEnabled': '80213dc0' in run['traceOnly'].lower().split(','),
        'planeFrames': re.findall(r'\[THPPlanes\] frame=(\d+)', log),
        'gpuHang': 'GPU Hang' in log, 'invalidPairedRefusal': 'Invalid paired execution' in log}
    if args.loop_observation:
        assert run['loopAddress'] == 0x80197498 and run['peekAddress'] == 0x8052B220 and run['peekWords'] == 32
        guest = output / 'output_47.cpp'
        report['ringObservation'] = summarize(log, dol, guest.read_text())
        paths = [guest, full / 'gx.cpp', full / 'hw_cp.cpp', full / 'fifo_parser.cpp',
            Path('experiments/wii-static-recomp/stock_ring_observation.py')]
        report['ringSourceHashes'] = {str(path): sha(path) for path in paths}
(output / ('audit-' + (args.tag or 'component') + '.json')).write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], 'guards=', report['guardCount'], 'modules=', report['changedModules'])

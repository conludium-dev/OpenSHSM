"""Verify exact context correction, retained link inputs and actual coverage."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
from stock_fp_context_patch import adapt_fp_context, adapt_lazy_fp_context, verify_fp_sdk

parser = argparse.ArgumentParser()
parser.add_argument('--tag')
parser.add_argument('--lazy-context', action='store_true')
args = parser.parse_args()
assert not (args.lazy_context and args.tag), 'Prepared lazy runtime must not be booted yet'
assert args.tag is None or re.fullmatch(r'[a-z0-9-]{1,40}', args.tag)
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base = root / ('window-fp-context' if args.lazy_context else 'window-thp-dcbz')
full = root / 'window-quantization'
output = root / ('window-fp-lazy-context' if args.lazy_context else 'window-fp-context')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert sha(base / 'build.json') == build['baseBuildSha256']
assert sha(full / 'build.json') == build['fullBuildSha256']
parent = json.loads((full / 'build.json').read_text())
previous = json.loads((base / 'build.json').read_text())
assert (output / 'ios.cpp').read_text() == (adapt_lazy_fp_context((base / 'ios.cpp').read_text()) if args.lazy_context
    else adapt_fp_context((full / 'ios.cpp').read_text()))
assert sha(output / 'ios.cpp') == build['sourceSha256'] and sha(output / 'ios.cpp.o') == build['objectSha256']
assert sha(full / 'include/runtime/cpu_context.h') == parent['cpuHeaderSha256']
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
assert verify_fp_sdk((full / 'output_38.cpp').read_text(), dol_path.read_bytes()) == build['sdkSites']
assert len(build['retainedRuntimeMembers']) == 44
for member, digest in build['retainedRuntimeMembers'].items():
    for archive in (output / 'libnwiiruntime.a', full / 'libnwiiruntime.a'):
        assert hashlib.sha256(subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])).hexdigest() == digest
assert subprocess.check_output(['/usr/bin/ar', '-p', str(output / 'libnwiiruntime.a'), 'ios.cpp.o']) == (output / 'ios.cpp.o').read_bytes()
assert sha(output / 'libnwiiruntime.a') == build['archiveSha256']
exe_name = 'OpenSHSMStockFPLazyContext' if args.lazy_context else 'OpenSHSMStockFPContext'
assert sha(output / exe_name) == build['executableSha256']
guest_parent = root / 'window-thp-dcbz' if args.lazy_context else base
guest_build = json.loads((guest_parent / 'build.json').read_text())
for path, digest in guest_build['retainedObjects'].items():
    assert sha(Path(path)) == digest
assert sha(guest_parent / 'output_37.cpp.o') == guest_build['objectSha256']
expected = list(previous['linkCommand'])
base_archive = (base if args.lazy_context else full) / 'libnwiiruntime.a'
expected[expected.index(str(base_archive))] = str(output / 'libnwiiruntime.a')
expected[expected.index('-o') + 1] = str(output / exe_name)
assert expected == build['linkCommand']
if args.lazy_context:
    component = root / 'fp-exception-lazy-component'
    contract = json.loads((component / 'report.json').read_text())
    assert contract['result'] == 'LAZY_HLE_FP_EXCEPTION_SDK_COMPONENT_PASS' and contract['lazyContext']
    assert (component / 'ios.cpp').read_bytes() == (output / 'ios.cpp').read_bytes()
    assert contract['dolSha256'] == sha(dol_path)
    for item in contract['inputs']:
        assert sha(Path(item['path'])) == item['sha256'], item['path']
    test = subprocess.run([str(component / 'fp-exception-contract'), str(dol_path.resolve())],
        capture_output=True, text=True, timeout=20)
    assert test.returncode == 0 and not test.stderr and test.stdout.strip() == contract['output']
    report = {'result': 'LAZY_FP_CONTEXT_PREPARED_PROVENANCE_PASS_NOT_BOOT_READY',
        'contract': test.stdout.strip(), 'retainedGuestObjects': len(guest_build['retainedObjects']) + 1,
        'retainedRuntimeMembers': 44, 'sdkInstructions': len(contract['sdkInstructions']),
        'limits': build['limits'] + contract['limits']}
    (output / 'audit-component.json').write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], report['contract'])
    raise SystemExit(0)
contract = json.loads((output / 'contract.json').read_text())
assert contract['parentBuildSha256'] == sha(output / 'build.json')
assert contract['cpuHeaderSha256'] == parent['cpuHeaderSha256']
assert contract['sourceSha256'] == sha(Path('experiments/wii-static-recomp/stock_fp_context_contract.cpp'))
assert contract['helperHeaderSha256'] == sha(output / 'context-helpers.h')
assert contract['executableSha256'] == sha(output / 'context-contract')
test = subprocess.run([str(output / 'context-contract')], capture_output=True, text=True, timeout=20)
assert test.returncode == 0 and test.stdout.strip() == contract['output']
report = {'result': 'FP_CONTEXT_CORRECTION_PROVENANCE_PASS', 'sdkSites': len(build['sdkSites']),
    'contract': test.stdout.strip(), 'limits': build['limits'] + contract['limits']}
if args.tag:
    prefix = root / ('window-fp-context-headless-windowed-' + args.tag)
    log_path, run_path = Path(str(prefix) + '.log'), Path(str(prefix) + '-result.json')
    run = json.loads(run_path.read_text())
    assert run['executableSha256'] == build['executableSha256'] and run['logSha256'] == sha(log_path)
    assert run['originalDolSha256'] == sha(dol_path)
    log = log_path.read_text(errors='replace')
    report['runtime'] = {'returncode': run['terminalReturncode'], 'deadlineReached': run['deadlineReached'],
        'runSha256': sha(run_path), 'gpuHangReported': 'GPU Hang' in log,
        'decoderCalls': len(re.findall(r'\[CALL\] 0x80209d80 ', log)),
        'planeRecords': re.findall(r'\[THPPlanes\] frame=(\d+)', log)}
(output / ('audit-' + (args.tag or 'component') + '.json')).write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], report.get('runtime', 'run unverified'))

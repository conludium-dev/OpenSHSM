"""Audit every full-rebuild consumer and actual observation coverage, not menu acceptance."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
from stock_quantization_patch import adapt_quantization
from stock_thp_observation import adapt_thp_calls

parser = argparse.ArgumentParser()
parser.add_argument('--tag')
args = parser.parse_args()
assert args.tag is None or re.fullmatch(r'[a-z0-9-]{1,40}', args.tag)
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base, output = root / 'window-locked-cache', root / 'window-quantization'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert sha(base / 'build.json') == build['baseBuildSha256']
parent = json.loads((base / 'build.json').read_text())
assert len(build['compiled']) == 124
header = output / 'include/runtime/cpu_context.h'
assert header.read_text() == adapt_quantization((base / 'include/runtime/cpu_context.h').read_text())
assert sha(header) == build['cpuHeaderSha256']
component = json.loads((root / 'quantization-contract/result.json').read_text())
corrected = next(row for row in component['records'] if row['variant'] == 'corrected')
assert sha(header) == corrected['headerSha256']
assert sha(root / 'quantization-contract/corrected-probe') == corrected['executableSha256']
quantization_test = subprocess.run([str(root / 'quantization-contract/corrected-probe')],
    capture_output=True, text=True, timeout=20)
assert quantization_test.returncode == 0 and quantization_test.stdout.strip() == corrected['output']
for name in ('carry_adapter.h', 'processor_adapter.h'):
    assert (base / name).read_bytes() == (output / name).read_bytes()
for item in build['compiled']:
    source, original = output / item['source'], base / item['source']
    parent_item = next(row for row in parent['compiled'] if row['object'] == item['object'])
    assert item['baseSourceSha256'] == parent_item['sourceSha256']
    assert item['arguments'] == [arg.replace(str(base), str(output)) for arg in parent_item['arguments']]
    assert sha(original) == item['baseSourceSha256']
    expected = adapt_thp_calls(original.read_text()) if source.name == 'os_hle_stubs.cpp' else original.read_text()
    assert source.read_text() == expected
    assert sha(source) == item['sourceSha256'] and sha(output / item['object']) == item['objectSha256']
    assert item['arguments'][:2] == ['-I', str(output / 'include')]
    assert not any(str(base) in arg for arg in item['arguments'])
    assert not any(arg in ('-DNDEBUG', '-ffast-math', '-Ofast') for arg in item['arguments'])
members = subprocess.check_output(['/usr/bin/ar', '-t', str(output / 'libnwiiruntime.a')], text=True).splitlines()
assert set(members) - {'__.SYMDEF'} == set(build['runtimeMembers'])
for member in build['runtimeMembers']:
    assert subprocess.check_output(['/usr/bin/ar', '-p', str(output / 'libnwiiruntime.a'), member]) == (output / member).read_bytes()
assert sha(output / 'libnwiiruntime.a') == build['archiveSha256']
assert sha(output / 'OpenSHSMStockQuantization') == build['executableSha256']
assert sha(output / 'locked-cache-contract') == build['contractExecutableSha256']
assert not any(str(base) in arg for arg in build['linkCommand'])
test = subprocess.run([str(output / 'locked-cache-contract')], capture_output=True, text=True, timeout=20)
assert test.returncode == 0 and test.stdout.strip() == build['contract']
report = {'result': 'QUANTIZATION_FULL_REBUILD_PROVENANCE_PASS', 'compiled': 124,
    'quantizationComponent': quantization_test.stdout.strip(),
    'buildSha256': sha(output / 'build.json'), 'limits': build['limits']}
if args.tag:
    prefix = root / ('window-quantization-headless-windowed-' + args.tag)
    run_path, log_path = Path(str(prefix) + '-result.json'), Path(str(prefix) + '.log')
    run = json.loads(run_path.read_text())
    assert run['executableSha256'] == build['executableSha256'] and sha(log_path) == run['logSha256']
    assert run['originalDolSha256'] == sha(Path('work/private-game/disc/DATA/sys/main.dol'))
    log = log_path.read_text(errors='replace')
    report['runtime'] = {'returncode': run['terminalReturncode'], 'deadlineReached': run['deadlineReached'],
        'runSha256': sha(run_path), 'gpuHangReported': 'GPU Hang' in log,
        'decoderCalls': len(re.findall(r'\[CALL\] 0x80209d80 ', log)),
        'planeRecords': re.findall(r'\[THPPlanes\] frame=(\d+)', log),
        'captures': {path.name: sha(path) for path in root.glob('window-quantization-' + args.tag + '-thp-*.bin')}}
(output / ('audit-' + (args.tag or 'component') + '.json')).write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], report.get('runtime', 'run unverified'))

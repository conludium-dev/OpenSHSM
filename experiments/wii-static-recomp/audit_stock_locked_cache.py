"""Verify the full ABI rebuild and original DMA lowering; do not certify THP pixels."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
from stock_locked_cache_patch import adapt_cpu_header, adapt_processor_header, adapt_interpreter, lower_dma

parser = argparse.ArgumentParser()
parser.add_argument('--tag')
args = parser.parse_args()
assert args.tag is None or re.fullmatch(r'[a-z0-9-]{1,40}', args.tag)
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-locked-cache'
experiment = Path('experiments/wii-static-recomp')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
dol = dol_path.read_bytes()
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
cpu_base = root / 'export/nWiiRuntime/include/runtime/cpu_context.h'
assert sha(cpu_base) == build['cpuBaseHeaderSha256']
assert sha(output / 'include/runtime/cpu_context.h') == build['cpuHeaderSha256']
assert (output / 'include/runtime/cpu_context.h').read_text() == adapt_cpu_header(cpu_base.read_text())
assert sha(output / 'processor_adapter.h') == build['processorHeaderSha256']
assert (output / 'processor_adapter.h').read_text() == adapt_processor_header((experiment / 'processor_adapter.h').read_text())
assert (output / 'carry_adapter.h').read_bytes() == (root / 'window-hid2-carry/carry_adapter.h').read_bytes()
assert sha(root / 'window-hid2-carry/libnwiiruntime.a') == build['baseArchiveSha256']
assert len(build['compiled']) == 124
names = {item['object'] for item in build['compiled']}
assert all(f'output_{i}.cpp.o' in names for i in range(75))
assert {'main.cpp.o', 'main_output.cpp.o', 'contract-entry.cpp.o'} <= names
sites = []
for item in build['compiled']:
    source, original = output / item['source'], Path(item['baseSource'])
    assert sha(original) == item['baseSourceSha256']
    assert sha(source) == item['sourceSha256']
    assert sha(output / item['object']) == item['objectSha256']
    assert item['arguments'][:2] == ['-I', str(output / 'include')]
    assert not any(flag in item['arguments'] for flag in ('-DNDEBUG', '-ffast-math', '-Ofast'))
    expected = original.read_text()
    if re.fullmatch(r'output_\d+\.cpp', source.name):
        expected, changes = lower_dma(expected, dol)
        sites += [dict(change, file=source.name) for change in changes]
        assert '-O2' in item['arguments'] and '-ffp-contract=off' in item['arguments']
    elif source.name == 'interpreter.cpp':
        expected = adapt_interpreter(expected)
    assert source.read_text() == expected
assert sites == build['dmaSites'] and len(sites) == 6
assert sha(output / 'libnwiiruntime.a') == build['archiveSha256']
assert sha(output / 'OpenSHSMStockLockedCache') == build['executableSha256']
assert sha(output / 'locked-cache-contract') == build['contractExecutableSha256']
test = subprocess.run([str(output / 'locked-cache-contract')], capture_output=True, text=True, timeout=20)
assert test.returncode == 0 and test.stdout.strip() == build['contract']
report = {'result': 'LOCKED_CACHE_FULL_ABI_REBUILD_AND_COMPONENT_PASS', 'compiled': len(names),
    'dmaSites': len(sites), 'contract': test.stdout.strip(), 'buildSha256': sha(output / 'build.json'),
    'originalDolSha256': sha(dol_path), 'limits': build['limits']}
if args.tag:
    prefix = root / ('window-locked-cache-headless-windowed-' + args.tag)
    log_path, run_path = Path(str(prefix) + '.log'), Path(str(prefix) + '-result.json')
    run = json.loads(run_path.read_text())
    assert run['logSha256'] == sha(log_path)
    assert run['executableSha256'] == build['executableSha256'] and run['originalDolSha256'] == sha(dol_path)
    log = log_path.read_text(errors='replace')
    report['runtime'] = {'terminalReturncode': run['terminalReturncode'], 'deadlineReached': run['deadlineReached'],
        'runSha256': sha(run_path), 'gpuHangReported': 'GPU Hang' in log,
        'dmaCommandCalls': len(re.findall(r'\[CALL\] 0x80213240 ', log)),
        'decoderCalls': len(re.findall(r'\[CALL\] 0x80209d80 ', log))}
(output / ('audit-' + (args.tag or 'component') + '.json')).write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], test.stdout.strip(), report.get('runtime', 'runtime unverified'))

"""Replace only existing IOS context serialization; retain original guest and runtime objects."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
from stock_fp_context_patch import adapt_fp_context, adapt_lazy_fp_context, verify_fp_sdk

parser = argparse.ArgumentParser()
parser.add_argument('--lazy-context', action='store_true', help='Prepare lazy-bank IOS runtime; do not boot without complete FP guards')
args = parser.parse_args()

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base, full = root / ('window-fp-context' if args.lazy_context else 'window-thp-dcbz'), root / 'window-quantization'
output = root / ('window-fp-lazy-context' if args.lazy_context else 'window-fp-context')
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((base / 'build.json').read_text())
parent = json.loads((full / 'build.json').read_text())
base_exe = 'OpenSHSMStockFPContext' if args.lazy_context else 'OpenSHSMStockTHPDCBZ'
assert sha(base / base_exe) == build['executableSha256']
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
sdk_sites = verify_fp_sdk((full / 'output_38.cpp').read_text(), dol_path.read_bytes())
item = next(row for row in parent['compiled'] if row['source'] == 'ios.cpp')
assert sha(full / 'ios.cpp') == item['sourceSha256']
source = output / 'ios.cpp'
source.write_text(adapt_lazy_fp_context((base / 'ios.cpp').read_text()) if args.lazy_context
    else adapt_fp_context((full / 'ios.cpp').read_text()))
obj = output / 'ios.cpp.o'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *item['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=120)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
archive = output / 'libnwiiruntime.a'
base_archive = (base if args.lazy_context else full) / 'libnwiiruntime.a'
shutil.copy2(base_archive, archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], check=True, capture_output=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
retained_runtime = {}
for member in parent['runtimeMembers']:
    if member == obj.name:
        continue
    before = subprocess.check_output(['/usr/bin/ar', '-p', str(base_archive), member])
    assert before == subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    retained_runtime[member] = hashlib.sha256(before).hexdigest()
command = list(build['linkCommand'])
command[command.index(str(base_archive))] = str(archive)
exe = output / ('OpenSHSMStockFPLazyContext' if args.lazy_context else 'OpenSHSMStockFPContext')
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=120)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
(output / 'build.json').write_text(json.dumps({'result': 'FP_LAZY_CONTEXT_PREPARED_NOT_BOOT_READY' if args.lazy_context else 'FP_CONTEXT_LAYOUT_CORRECTION',
    'baseBuildSha256': sha(base / 'build.json'), 'fullBuildSha256': sha(full / 'build.json'),
    'sourceSha256': sha(source), 'objectSha256': sha(obj), 'archiveSha256': sha(archive),
    'retainedRuntimeMembers': retained_runtime, 'executableSha256': sha(exe), 'sdkSites': sdk_sites,
    'linkCommand': command, 'arguments': item['arguments'],
    'lazyContext': args.lazy_context,
    'baseArchiveSha256': sha(base_archive),
    'limits': ['Lazy mode removes physical FPR/PS1/FPSCR serialization from existing IOS helpers; no new owner registry.',
        'Lazy mode must not be booted before full static/fallback FP exception guards and original SDK FPSCR lowering.',
        'Wii SDK paired storage64sites checked; only existing HLE serialization changed.',
        'Not proof of full FPU/FPSCR/lazy ownership/IRQ semantics or pixel/menu acceptance.']}, indent=2) + '\n')
print('Prepared lazy-bank runtime (NOT BOOT READY)' if args.lazy_context else 'Built FP context',
    ':64SDK instructions verified, all77guest objects/44runtime members retained')

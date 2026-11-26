"""Replace only the observed guest object on current fully rebuilt quantization runtime."""
from pathlib import Path
import hashlib
import json
import subprocess
import argparse
from stock_idct_observation import adapt_idct
from stock_dcbz_lowering import lower_dcbz

parser = argparse.ArgumentParser()
parser.add_argument('--dcbz', action='store_true')
args = parser.parse_args()

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base = root / 'window-quantization'
output = root / ('window-thp-dcbz' if args.dcbz else 'window-idct-observe')
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((base / 'build.json').read_text())
assert sha(base / 'OpenSHSMStockQuantization') == build['executableSha256']
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
item = next(row for row in build['compiled'] if row['source'] == 'output_37.cpp')
source = output / item['source']
assert sha(base / item['source']) == item['sourceSha256']
text, sites = adapt_idct((base / item['source']).read_text(), dol_path.read_bytes())
zero_sites = []
if args.dcbz:
    text, zero_sites = lower_dcbz(text, dol_path.read_bytes())
source.write_text(text)
obj = output / item['object']
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *item['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
command = list(build['linkCommand'])
command[command.index(str(base / item['object']))] = str(obj)
exe = output / ('OpenSHSMStockTHPDCBZ' if args.dcbz else 'OpenSHSMStockIDCTObserver')
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=120)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
retained = {str(base / row['object']): sha(base / row['object']) for row in build['compiled']
    if row['object'] != item['object'] and str(base / row['object']) in command}
assert len(retained) == 76
(output / 'build.json').write_text(json.dumps({'result': 'THP_DCBZ_WITH_OBSERVER' if args.dcbz else 'READ_ONLY_IDCT_OBSERVER', 'sites': sites,
    'zeroSites': zero_sites,
    'baseBuildSha256': sha(base / 'build.json'), 'sourceSha256': sha(source), 'objectSha256': sha(obj),
    'retainedObjects': retained, 'archiveSha256': sha(base / 'libnwiiruntime.a'),
    'executableSha256': sha(exe), 'arguments': item['arguments'], 'linkCommand': command,
    'limits': ['Read-only first6entries/32stores; host logging may change timing.',
        'Only original dcbz writes when enabled; no readiness/clock/callback forcing.',
        'Stock direct-memory approximation, not precise cache visibility/DCE exceptions/dcbz_l; no decoder correctness claim.']}, indent=2) + '\n')
print('Built IDCT observer:', len(sites), 'DOL-checked sites,76objects/full runtime archive retained')

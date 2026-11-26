"""Reuse callback diagnostics in the actually reached early numeric scope."""
from pathlib import Path
import hashlib
import json
import subprocess
import argparse
from stock_idct_callbacks import adapt_callbacks

parser = argparse.ArgumentParser()
parser.add_argument('--nonlocal-unwind', action='store_true')
args = parser.parse_args()

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base, full = root / 'window-idct-callbacks', root / 'window-quantization'
output = root / ('window-numeric-unwind' if args.nonlocal_unwind else 'window-numeric-callbacks')
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((base / 'build.json').read_text())
parent = json.loads((full / 'build.json').read_text())
assert sha(base / 'OpenSHSMStockIDCTCallbacks') == build['executableSha256']
item = next(row for row in parent['compiled'] if row['source'] == 'output_30.cpp')
assert sha(full / 'output_30.cpp') == item['sourceSha256']
dol = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
text, sites = adapt_callbacks((full / 'output_30.cpp').read_text(), dol.read_bytes(), numeric=True, nonlocal_unwind=args.nonlocal_unwind)
source, obj = output / 'output_30.cpp', output / 'output_30.cpp.o'
source.write_text(text)
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *item['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
command = list(build['linkCommand'])
command[command.index(str(full / 'output_30.cpp.o'))] = str(obj)
exe = output / ('OpenSHSMStockNumericUnwind' if args.nonlocal_unwind else 'OpenSHSMStockNumericCallbacks')
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=120)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
(output / 'build.json').write_text(json.dumps({'result': 'NUMERIC_CALLBACK_OBSERVER', 'sites': sites,
    'sourceSha256': sha(source), 'objectSha256': sha(obj), 'executableSha256': sha(exe),
    'baseBuildSha256': sha(base / 'build.json'), 'fullBuildSha256': sha(full / 'build.json'),
    'arguments': item['arguments'], 'linkCommand': command,
    'retainedInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file() and Path(arg).suffix in ('.o', '.a') and arg != str(obj)},
    'limits': ['Original callback called exactly once; host-only scoped diagnostics, logging may affect timing.',
        'Numeric candidate resume matches context/PC/SP, not a complete activation ID.',
        'Fixed shared matrix is not a numeric-function input; no correctness inferred from it.']}, indent=2) + '\n')
print('Built numeric callback observer;', len(sites), 'own-DOL-checked sites')

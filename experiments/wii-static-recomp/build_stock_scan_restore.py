"""Restore one original wrapper and dispatcher continuation range in a private build."""
from pathlib import Path
import hashlib
import json
import subprocess
import argparse
from stock_scan_restore import restore_guest, restore_dispatch

parser = argparse.ArgumentParser()
parser.add_argument('--continuation-routes', action='store_true')
args = parser.parse_args()
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
full, base = root / 'window-quantization', root / 'window-fp-guard'
output = root / ('window-scan-routes' if args.continuation_routes else 'window-scan-restore')
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((base / 'build.json').read_text())
parent = json.loads((full / 'build.json').read_text())
tables = json.loads((root / 'fp-guard-component/report.json').read_text())['tables']
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
mass = root.parent / 'mass-current/output_51.cpp'
guest, words = restore_guest((base / 'output_31.cpp').read_text(), mass.read_text(), dol_path.read_bytes(), tables)
dispatcher = restore_dispatch((full / 'main_output.cpp').read_text(), args.continuation_routes)
command = list(build['linkCommand'])
compiled = []
for name, text, original in [('output_31.cpp', guest, base / 'output_31.cpp'),
    ('main_output.cpp', dispatcher, full / 'main_output.cpp')]:
    item = next(row for row in parent['compiled'] if row['source'] == name)
    source, obj = output / name, output / (name + '.o')
    source.write_text(text)
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *item['arguments'],
        '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=120)
    (output / (name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    command[command.index(str(original.with_name(name + '.o')))] = str(obj)
    compiled.append({'source': name, 'sourceSha256': sha(source), 'objectSha256': sha(obj),
        'originalPath': str(original), 'originalSha256': sha(original), 'arguments': item['arguments']})
exe = output / ('OpenSHSMStockScanRoutes' if args.continuation_routes else 'OpenSHSMStockScanRestore')
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=60)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
(output / 'build.json').write_text(json.dumps({'result': 'ORIGINAL_SCAN_WRAPPER_RESTORED_UNVERIFIED',
    'compiled': compiled, 'originalWords': words, 'massSourceSha256': sha(mass),
    'continuationRoutes': args.continuation_routes,
    'baseBuildSha256': sha(base / 'build.json'), 'fullBuildSha256': sha(full / 'build.json'),
    'executableSha256': sha(exe), 'linkCommand': command,
    'retainedInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file()
        and Path(arg).suffix in ('.o', '.a') and arg not in {str(output / 'output_31.cpp.o'), str(output / 'main_output.cpp.o')}},
    'limits': ['Original wrapper76words/8FPguards/full continuation range; original callees retained, no host sscanf.',
        'Native/original PPC output and full boot not verified by build alone; real OSReport80213EA0 unchanged.']}, indent=2) + '\n')
print('Built restored original scan wrapper +dispatcher; 76DOL words/8FP guards, retained runtime unchanged')

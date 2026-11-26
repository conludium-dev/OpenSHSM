"""Add shared numeric-reader observation to the existing measured UI-loading runtime."""
from pathlib import Path
import hashlib
import json
import subprocess
import argparse
from stock_numeric_reader import adapt, flight_header

parser = argparse.ArgumentParser()
parser.add_argument('--flight', action='store_true')
args = parser.parse_args()
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base = root / 'window-subtitle-progress'
output = root / ('window-numeric-flight' if args.flight else 'window-numeric-reader')
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((base / 'build.json').read_text())
assert sha(base / 'OpenSHSMStockSubtitleProgress') == build['executableSha256']
command = list(build['linkCommand'])
original = next(Path(arg) for arg in command if Path(arg).name == 'output_31.cpp.o').with_suffix('')
dol = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
source, obj = output / 'output_31.cpp', output / 'output_31.cpp.o'
source.write_text(adapt(original.read_text(), dol.read_bytes(), args.flight))
if args.flight:
    (output / 'stock_numeric_reader_flight.h').write_text(flight_header(Path('experiments/wii-static-recomp/stock_numeric_reader.h').read_text()))
full = json.loads((root / 'window-quantization/build.json').read_text())
arguments = next(row['arguments'] for row in full['compiled'] if row['source'] == 'output_31.cpp')
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=120)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
command[command.index(str(original) + '.o')] = str(obj)
exe = output / ('OpenSHSMStockNumericFlight' if args.flight else 'OpenSHSMStockNumericReader')
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=60)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
(output / 'build.json').write_text(json.dumps({'result': 'READ_ONLY_NUMERIC_READER_BUILT',
    'baseBuildSha256': sha(base / 'build.json'), 'originalPath': str(original), 'originalSha256': sha(original),
    'sourceSha256': sha(source), 'objectSha256': sha(obj), 'arguments': arguments,
    'headerSha256': sha(Path('experiments/wii-static-recomp/stock_numeric_reader.h')),
    'flight': args.flight,
    'flightHeaderSha256': sha(output / 'stock_numeric_reader_flight.h') if args.flight else None,
    'linkCommand': command, 'executableSha256': sha(exe),
    'retainedInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file()
        and Path(arg).suffix in ('.o', '.a') and arg != str(obj)},
    'limits': ['Two original entry/return hooks;8192calls/80byte input prefixes, host-only pending correlation.',
        'String reader interpretation only for original8019D3AC; other callback types are not interpreted as strings.',
        'Raw FPR1 bank may belong to another thread when MSR.FP is clear; no blanket logical mismatch or whole IRQ oracle.']}, indent=2) + '\n')
print('Built shared original numeric-reader observer; one guest object replaced')

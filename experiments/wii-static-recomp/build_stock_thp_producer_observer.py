"""Add producer and SDK callback boundaries to the existing movie-observed game."""
from pathlib import Path
import hashlib
import json
import subprocess
import argparse
from stock_thp_producer_observation import adapt
from stock_thp_chain_observation import adapt as adapt_chain, chain_header
from stock_thp_dma_observation import adapt as adapt_dma, dma_header

parser = argparse.ArgumentParser()
parser.add_argument('--chain', action='store_true')
parser.add_argument('--dma', action='store_true')
args = parser.parse_args()
args.chain = args.chain or args.dma

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base, output = root / 'window-movie-update', root / 'window-movie-producer'
if args.chain:
    output = root / 'window-movie-chain'
if args.dma:
    output = root / 'window-movie-dma'
output.mkdir(exist_ok=True)
if args.chain:
    header_name = 'stock_thp_dma_observation.h' if args.dma else 'stock_thp_chain_observation.h'
    (output / header_name).write_text((dma_header if args.dma else chain_header)(Path('experiments/wii-static-recomp/stock_thp_producer_observation.h').read_text()))
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((base / 'build.json').read_text())
assert sha(base / 'OpenSHSMStockMovieUpdate') == build['executableSha256']
command = list(build['linkCommand'])
full = json.loads((root / 'window-quantization/build.json').read_text())
dol = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
records = []
for module in (11, 39):
    name = f'output_{module}.cpp'
    original = next(Path(arg) for arg in command if Path(arg).name == name + '.o').with_suffix('')
    source, obj = output / name, output / (name + '.o')
    source.write_text((adapt_dma if args.dma else adapt_chain if args.chain else adapt)(original.read_text(), dol.read_bytes(), module))
    arguments = next(row['arguments'] for row in full['compiled'] if row['source'] == name)
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
        '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=120)
    (output / (name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    command[command.index(str(original) + '.o')] = str(obj)
    records.append({'module': module, 'originalPath': str(original), 'originalSha256': sha(original),
        'sourceSha256': sha(source), 'objectSha256': sha(obj), 'arguments': arguments})
exe = output / ('OpenSHSMStockMovieDMA' if args.dma else 'OpenSHSMStockMovieChain' if args.chain else 'OpenSHSMStockMovieProducer')
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=60)
(output / 'build.json').write_text(json.dumps({'baseBuildSha256': sha(base / 'build.json'),
    'records': records, 'headerSha256': sha(Path('experiments/wii-static-recomp/stock_thp_producer_observation.h')),
    'chain': args.chain,
    'dma': args.dma,
    'chainHeaderSha256': sha(output / header_name) if args.chain else None,
    'queueHeaderSha256': sha(Path('experiments/wii-static-recomp/stock_thp_queue_observation.h')),
    'linkCommand': command, 'executableSha256': sha(exe),
    'retainedInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file()
        and Path(arg).suffix in ('.o', '.a') and arg not in {str(output / 'output_11.cpp.o'), str(output / 'output_39.cpp.o')}},
    'limits': ['23 original non-FP boundaries/first64then60 perpoint + phase changes/8192cap, host-only read observation.' if args.dma
        else '17 original non-FP boundaries/first64then60 perpoint + phase changes/8192cap, host-only read observation.' if args.chain
        else '11 original non-FP boundaries/first16then60 perpoint/8192cap, host-only read observation.',
        'SDK guard/callback and movie F4 data, no forced callback/clock/audio/counter state.',
        'No complete call/IRQ pairing or original behavior acceptance from build.']}, indent=2) + '\n')
print('Built original movie producer observer; two guest objects changed')

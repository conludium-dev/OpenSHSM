"""Read-only producer helper fixture, not SDK callback/game execution."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import argparse
import re

parser = argparse.ArgumentParser()
parser.add_argument('--chain', action='store_true')
parser.add_argument('--dma', action='store_true')
parser.add_argument('--tag', default='')
args = parser.parse_args()
args.chain = args.chain or args.dma
assert args.tag == '' or re.fullmatch('[a-z0-9-]{1,40}', args.tag)

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-movie-producer'
if args.chain:
    output = root / 'window-movie-chain'
if args.dma:
    output = root / 'window-movie-dma'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
source = Path('experiments/wii-static-recomp/stock_thp_chain_contract.cpp' if args.chain
    else 'experiments/wii-static-recomp/stock_thp_producer_contract.cpp').resolve()
compiled_source = source
if args.dma:
    compiled_source = output / 'dma-contract.cpp'
    text = source.read_text().replace('"stock_thp_chain_observation.h"', '"stock_thp_dma_observation.h"')
    marker = '0x8009BB48u, 0x8009BB4Cu, 0x8009BAECu, 0x8009BBBCu})'
    assert text.count(marker) == 1
    text = text.replace(marker, '0x8009BB48u, 0x8009BB4Cu, 0x8009BAECu, 0x8009BBBCu,\n'
        '        0x8009BB34u, 0x8009BB58u, 0x8009BB7Cu, 0x8009BB80u, 0x8009BB9Cu, 0x8009BBB8u})')
    compiled_source.write_text(text)
obj, exe = output / 'contract.cpp.o', output / 'observer-contract'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *build['records'][0]['arguments'], '-I', str(output),
    '-c', str(compiled_source), '-o', str(obj)], capture_output=True, text=True, timeout=60)
(output / 'contract-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
command = list(build['linkCommand'])
full = root / 'window-quantization'
command[command.index(str(full / 'main.cpp.o'))] = str(full / 'contract-entry.cpp.o')
command.insert(1, str(obj))
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=60)
prefix = 'component' + ('-' + args.tag if args.tag else '')
capture = output / (prefix + '-movie-producer.jsonl')
assert not capture.exists()
env = {key: value for key, value in os.environ.items() if not key.startswith(('SHSM_', 'NWII_'))}
env['NWII_THPDUMP'] = str(output / prefix)
result = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=20)
(output / 'contract.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
rows = [json.loads(line) for line in capture.read_text().splitlines()]
assert len(rows) == (87 if args.dma else 81 if args.chain else 11) and len({row['pc'] for row in rows}) == (23 if args.dma else 17 if args.chain else 11)
if args.chain:
    assert rows[-1]['pc'] == 0x8009BBF0 and rows[-1]['hits'] == 72 and rows[-1]['phaseChanged']
    assert rows[-2]['hits'] == 64 and not rows[-2]['phaseChanged']
assert all(row['sdkStateHex'][-8:] == '8009ba88' for row in rows)
(output / 'component.json').write_text(json.dumps({'result': 'MOVIE_PRODUCER_HELPER_COMPONENT_PASS',
    'events': len(rows), 'buildSha256': sha(output / 'build.json'), 'sourceSha256': sha(source),
    'compiledSourceSha256': sha(compiled_source),
    'objectSha256': sha(obj), 'executableSha256': sha(exe), 'captureSha256': sha(capture), 'capturePath': str(capture),
    'logSha256': sha(output / 'contract.log'),
    'limits': ['Synthetic23-point/first64/phase-change serialization and selectedstateRAMpreservation only, not original IRQ/producer/SDK execution.' if args.dma
        else 'Synthetic17-point/first64/phase-change serialization and selectedstateRAMpreservation only, not original IRQ/producer/SDK execution.' if args.chain
        else 'Synthetic11-point serialization/selectedstateRAMpreservation only, not original IRQ/producer/SDK execution.']}, indent=2) + '\n')
print('MOVIE_PRODUCER_HELPER_COMPONENT_PASS')

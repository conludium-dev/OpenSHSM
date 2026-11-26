"""Replace two read-only observed modules on the current verified consumer runtime."""
from pathlib import Path
import hashlib
import json
import subprocess
import argparse
from stock_loading_observation import adapt

parser = argparse.ArgumentParser()
parser.add_argument('--payloads', action='store_true')
args = parser.parse_args()
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base = root / 'window-scan-consume'
output = root / ('window-loading-payload' if args.payloads else 'window-loading-observe')
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((base / 'build.json').read_text())
assert sha(base / 'OpenSHSMStockScanConsumer') == build['executableSha256']
full = json.loads((root / 'window-quantization/build.json').read_text())
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
command = list(build['linkCommand'])
compiled = []
for index in (30, 32):
    name = f'output_{index}.cpp'
    original = next(Path(arg) for arg in command if Path(arg).name == name + '.o').with_suffix('')
    source, obj = output / name, output / (name + '.o')
    source.write_text(adapt(original.read_text(), dol_path.read_bytes(), index, args.payloads))
    arguments = next(item for item in full['compiled'] if item['source'] == name)['arguments']
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
        '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=120)
    (output / (name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    command[command.index(str(original) + '.o')] = str(obj)
    compiled.append({'index': index, 'originalPath': str(original), 'originalSha256': sha(original),
        'sourceSha256': sha(source), 'objectSha256': sha(obj), 'arguments': arguments})
exe = output / ('OpenSHSMStockLoadingPayload' if args.payloads else 'OpenSHSMStockLoadingObserver')
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=60)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
(output / 'build.json').write_text(json.dumps({'result': 'READ_ONLY_LOADING_OBSERVER_BUILT', 'compiled': compiled,
    'baseBuildSha256': sha(base / 'build.json'), 'linkCommand': command, 'executableSha256': sha(exe),
    'headerSha256': sha(Path('experiments/wii-static-recomp/stock_loading_observation.h')),
    'payloads': args.payloads,
    'payloadHeaderSha256': sha(Path('experiments/wii-static-recomp/stock_loading_payload_observation.h')) if args.payloads else None,
    'retainedInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file() and Path(arg).suffix in ('.o', '.a')
        and arg not in {str(output / f'output_{index}.cpp.o') for index in (30, 32)}},
    'limits': ['Read-only RAM/host-clock observations, no guest state changes;512callbacks, sampled main-loop boundaries.',
        'Pairing by CPUContext/SP/request, not complete activation/IRQ snapshot; request words named by offsets only.',
        'Host logging changes throughput; emitted build is not callback/boot behavior acceptance.']}, indent=2) + '\n')
print('Built read-only loading observer; two guest objects replaced, runtime retained')

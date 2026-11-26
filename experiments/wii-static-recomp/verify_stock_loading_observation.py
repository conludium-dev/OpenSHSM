"""Verify read-only observer helper with the same current runtime/CPU ABI."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--payloads', action='store_true')
args = parser.parse_args()
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / ('window-loading-payload' if args.payloads else 'window-loading-observe')
full = root / 'window-quantization'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
source = Path('experiments/wii-static-recomp/' + ('stock_loading_payload_contract.cpp' if args.payloads else 'stock_loading_observation_contract.cpp')).resolve()
obj, exe = output / 'contract.cpp.o', output / 'observer-contract'
arguments = next(row['arguments'] for row in json.loads((full / 'build.json').read_text())['compiled'] if row['source'] == 'output_30.cpp')
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=60)
(output / 'contract-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
command = list(build['linkCommand'])
command[command.index(str(full / 'main.cpp.o'))] = str(full / 'contract-entry.cpp.o')
command.insert(1, str(obj))
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=60)
(output / 'contract-link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
capture = output / 'component-loading.jsonl'
assert not capture.exists()
env = {key: value for key, value in os.environ.items() if not key.startswith(('SHSM_', 'NWII_'))}
env['NWII_THPDUMP'] = str(output / 'component')
result = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=20)
(output / 'contract.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
rows = [json.loads(line) for line in capture.read_text().splitlines()]
assert [row['event'] for row in rows] == ['frame-before', 'callback-before', 'callback-after', 'frame-after']
assert rows[1]['id'] == rows[2]['id'] == 0 and rows[0]['id'] == rows[3]['id'] == 1
assert rows[1]['request'] == rows[2]['request'] == 0x80600200
assert rows[1]['callback'] == rows[2]['callback'] == 0x800EF000
if args.payloads:
    assert (output / 'component-payload0.bin').read_bytes() == bytes(range(100, 116))
    assert not (output / 'component-payload1.bin').exists()
report = {'result': 'LOADING_OBSERVER_HELPER_COMPONENT_PASS', 'events': 4,
    'buildSha256': sha(output / 'build.json'), 'sourceSha256': sha(source), 'objectSha256': sha(obj),
    'headerSha256': sha(Path('experiments/wii-static-recomp/stock_loading_observation.h')),
    'payloadHeaderSha256': sha(Path('experiments/wii-static-recomp/stock_loading_payload_observation.h')) if args.payloads else None,
    'baseContractSha256': sha(Path('experiments/wii-static-recomp/stock_loading_observation_contract.cpp')),
    'executableSha256': sha(exe), 'captureSha256': sha(capture), 'logSha256': sha(output / 'contract.log'),
    'command': command, 'linkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file() and Path(arg).suffix in ('.o', '.a')},
    'limits': ['Helper state/RAM preservation and pairing fixture; no original callback or main-loop execution in this component.']}
(output / 'component.json').write_text(json.dumps(report, indent=2) + '\n')
print(report['result'])

"""Verify read-only subtitle helper on the same CPU ABI/runtime, not original loader execution."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output, full = root / 'window-subtitle-progress', root / 'window-quantization'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
source = Path('experiments/wii-static-recomp/stock_subtitle_progress_contract.cpp').resolve()
obj, exe = output / 'contract.cpp.o', output / 'observer-contract'
arguments = build['arguments']
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
capture = output / 'component-subtitle-progress.jsonl'
assert not capture.exists()
env = {key: value for key, value in os.environ.items() if not key.startswith(('SHSM_', 'NWII_'))}
env['NWII_THPDUMP'] = str(output / 'component')
result = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=20)
(output / 'contract.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
rows = [json.loads(line) for line in capture.read_text().splitlines()]
assert [row['event'] for row in rows] == ['script', 'cue', 'time-before', 'time-after', 'cue-after', 'load-after']
assert [row['serial'] for row in rows] == list(range(6))
assert rows[-1]['scripts'] == rows[-1]['cues'] == 1
assert rows[2]['inputHex'] == b'1.25'.hex() and rows[3]['timeHex'] == '3fa00000'
report = {'result': 'SUBTITLE_PROGRESS_HELPER_COMPONENT_PASS', 'events': 6,
    'buildSha256': sha(output / 'build.json'), 'sourceSha256': sha(source), 'objectSha256': sha(obj),
    'baseContractSha256': sha(Path('experiments/wii-static-recomp/stock_loading_observation_contract.cpp')),
    'headerSha256': sha(Path('experiments/wii-static-recomp/stock_subtitle_progress.h')),
    'executableSha256': sha(exe), 'captureSha256': sha(capture), 'logSha256': sha(output / 'contract.log'),
    'linkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file() and Path(arg).suffix in ('.o', '.a')},
    'limits': ['Helper preservation/event fields and baseline metadata fixture; no original subtitle loader execution here.']}
(output / 'component.json').write_text(json.dumps(report, indent=2) + '\n')
print(report['result'])

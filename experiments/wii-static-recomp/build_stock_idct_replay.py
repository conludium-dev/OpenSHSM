"""Link captured whole-IDCT component replay against current exact guest objects/runtime."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base = root / 'window-fp-context'
full = root / 'window-quantization'
output = root / 'idct-block-replay'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((base / 'build.json').read_text())
parent = json.loads((full / 'build.json').read_text())
arguments = next(row['arguments'] for row in parent['compiled'] if row['source'] == 'locked-cache-contract.cpp')
source = Path('experiments/wii-static-recomp/stock_idct_replay.cpp').resolve()
obj = output / 'probe.cpp.o'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=60)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
command = list(build['linkCommand'])
command[command.index(str(full / 'main.cpp.o'))] = str(full / 'contract-entry.cpp.o')
command.insert(1, str(obj))
exe = output / 'idct-replay'
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=120)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
(output / 'build.json').write_text(json.dumps({'sourceSha256': sha(source), 'objectSha256': sha(obj),
    'executableSha256': sha(exe), 'baseBuildSha256': sha(base / 'build.json'), 'linkCommand': command,
    'cpuHeaderSha256': sha(full / 'include/runtime/cpu_context.h'),
    'linkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file() and Path(arg).suffix in ('.o', '.a')},
    'limits': ['Captured native-boot input, standalone whole native IDCT replay without queued IRQ/callback events.',
        'Not original Wii reference execution; full MMU/IRQ/environment not snapshotted.',
        'Guest code and captured entry state unchanged; no fallback pixel replacement.']}, indent=2) + '\n')
print('Built standalone whole IDCT replay')

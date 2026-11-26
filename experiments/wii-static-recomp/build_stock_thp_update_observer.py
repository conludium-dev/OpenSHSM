"""Add four original movie-update checkpoints to the existing queue-observed runtime."""
from pathlib import Path
import hashlib
import json
import subprocess
from stock_thp_update_observation import adapt

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base, output = root / 'window-movie-queues', root / 'window-movie-update'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((base / 'build.json').read_text())
assert sha(base / 'OpenSHSMStockMovieQueues') == build['executableSha256']
command = list(build['linkCommand'])
original = next(Path(arg) for arg in command if Path(arg).name == 'output_11.cpp.o').with_suffix('')
dol = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
source, obj = output / 'output_11.cpp', output / 'output_11.cpp.o'
source.write_text(adapt(original.read_text(), dol.read_bytes()))
full = json.loads((root / 'window-quantization/build.json').read_text())
arguments = next(row['arguments'] for row in full['compiled'] if row['source'] == 'output_11.cpp')
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=120)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
command[command.index(str(original) + '.o')] = str(obj)
exe = output / 'OpenSHSMStockMovieUpdate'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=60)
(output / 'build.json').write_text(json.dumps({'baseBuildSha256': sha(base / 'build.json'),
    'originalPath': str(original), 'originalSourceSha256': sha(original), 'sourceSha256': sha(source),
    'objectSha256': sha(obj), 'arguments': arguments,
    'headerSha256': sha(Path('experiments/wii-static-recomp/stock_thp_update_observation.h')),
    'queueHeaderSha256': sha(Path('experiments/wii-static-recomp/stock_thp_queue_observation.h')),
    'linkCommand': command, 'executableSha256': sha(exe),
    'retainedInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file()
        and Path(arg).suffix in ('.o', '.a') and arg != str(obj)},
    'limits': ['Four original non-FP checkpoints; active8046BB40+F8 and raw state fields only.',
        'First16/every60 per point,4096cap; no forced update, recycling, clocks, queue success.',
        'No paired call/IRQ activation identity or original behavior acceptance from build.']}, indent=2) + '\n')
print('Built original movie-update observer; one guest object changed')

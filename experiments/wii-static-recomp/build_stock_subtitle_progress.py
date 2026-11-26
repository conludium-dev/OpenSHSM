"""Replace one observed subtitle module on the exact owned-resource capture runtime."""
from pathlib import Path
import hashlib
import json
import subprocess
from stock_subtitle_progress import adapt

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base, output = root / 'window-loading-payload', root / 'window-subtitle-progress'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((base / 'build.json').read_text())
assert sha(base / 'OpenSHSMStockLoadingPayload') == build['executableSha256']
command = list(build['linkCommand'])
original = next(Path(arg) for arg in command if Path(arg).name == 'output_16.cpp.o').with_suffix('')
dol = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
source, obj = output / 'output_16.cpp', output / 'output_16.cpp.o'
source.write_text(adapt(original.read_text(), dol.read_bytes()))
full = json.loads((root / 'window-quantization/build.json').read_text())
arguments = next(row['arguments'] for row in full['compiled'] if row['source'] == 'output_16.cpp')
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=120)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
command[command.index(str(original) + '.o')] = str(obj)
exe = output / 'OpenSHSMStockSubtitleProgress'
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=60)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
(output / 'build.json').write_text(json.dumps({'result': 'READ_ONLY_SUBTITLE_PROGRESS_BUILT',
    'baseBuildSha256': sha(base / 'build.json'), 'originalPath': str(original), 'originalSha256': sha(original),
    'sourceSha256': sha(source), 'objectSha256': sha(obj), 'arguments': arguments,
    'headerSha256': sha(Path('experiments/wii-static-recomp/stock_subtitle_progress.h')),
    'linkCommand': command, 'executableSha256': sha(exe),
    'retainedInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file()
        and Path(arg).suffix in ('.o', '.a') and arg != str(obj)},
    'limits': ['Host-only six original checkpoints/32768events/80byte numeric strings, no guest writes/stateforcing.',
        'Cue/time-after hooks follow completed FP stores to avoid counting an unavailable-instruction retry as another cue.',
        'Host logging affects throughput; counts are observed entries, not assumed original totals or full IRQ activation identities.']}, indent=2) + '\n')
print('Built original subtitle progress observer; one guest object replaced, runtime retained')

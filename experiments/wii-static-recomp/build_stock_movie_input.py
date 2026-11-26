"""Extend the existing movie observer with private bounded input capture, keeping all guest sources identical."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-movie-input'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-bounds-lookup/build.json'
parent = json.loads(parent_path.read_text())
for path, digest in {**parent['dependencies'], **parent['retainedInputs']}.items():
    assert sha(Path(path)) == digest
component_path = root / 'movie-packet-metadata/observer-component.json'
component = json.loads(component_path.read_text())
helper = public / 'stock_movie_input.h'
assert component['headerSha256'] == sha(helper)
assert component['result'] == 'MOVIE_INPUT_COMPONENT_READ_ONLY_CAP_EXCLUSIVE_FILES_PASS'
original_header = root / 'window-cpu-time/stock_movie_timing.h'
patches = [('#include <time.h>', '#include <time.h>\n#include "stock_movie_input.h"'),
    ('    timespec cpu_time{};', '    stock_movie_input::observe(ctx, site, serial);\n    timespec cpu_time{};')]
text = original_header.read_text()
for before, after in patches:
    assert text.count(before) == 1
    text = text.replace(before, after)
header = output / original_header.name
header.write_text(text)
(output / helper.name).write_bytes(helper.read_bytes())
guard = output / 'constant_fp_guard.h'
guard.write_bytes((root / 'window-cpu-time/constant_fp_guard.h').read_bytes())
flags = json.loads((root / 'window-cpu-time/build.json').read_text())['changes']
command = list(parent['linkCommand'])
changes = {}
for unit in (11, 37):
    old = next(Path(arg) for arg in command if Path(arg).name == f'output_{unit}.cpp.o')
    original = old.with_suffix('')
    source, obj = output / original.name, output / old.name
    source.write_bytes(original.read_bytes())
    arguments = flags[str(unit)]['arguments']
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
        '-I', str(original.parent), '-I', str(root / 'headless-psq-scale'), '-I', str(root / 'window-movie-dma'),
        '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
    (output / f'compile-{unit}.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-2500:]
    command[command.index(str(old))] = str(obj)
    changes[str(unit)] = {'originalPath': str(original), 'originalSha256': sha(original),
        'sourceSha256': sha(source), 'objectSha256': sha(obj), 'arguments': arguments}
exe = output / 'OpenSHSMStockMovieInput'
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2500:]
inputs = {}
for arg in command:
    if Path(arg).suffix in ('.o', '.a') and arg not in [str(output / f'output_{unit}.cpp.o') for unit in (11, 37)]:
        path = (Path(arg) if Path(arg).is_absolute() else root / 'export/build' / arg).resolve()
        inputs[str(path)] = sha(path)
(output / 'build.json').write_text(json.dumps({
    'result': 'BOUNDED_MOVIE_INPUT_OBSERVER_BUILT_LIVE_UNVERIFIED', 'parentBuildSha256': sha(parent_path),
    'componentSha256': sha(component_path), 'headerPatches': patches, 'changes': changes,
    'linkCommand': command, 'executableSha256': sha(exe), 'retainedInputs': inputs,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), helper, original_header, header, guard]},
    'limits': ['Existing observer only; unit11/37 source byte-identical, master/runtime/main/audio/clock retained.',
        'Pure bounded direct RAM access, no MMU read/cache/device operations or guest writes.',
        'Raw descriptorField4 role inferred from original output descriptor store, not unique frame ID proof.',
        'Capture before caller timestamp; diagnostic file IO still changes scheduling/cache costs.',
        'Actual original packet/live/full-frame verification pending, no default promotion.']}, indent=2) + '\n')
print('BOUNDED_MOVIE_INPUT_OBSERVER_BUILT_LIVE_UNVERIFIED')

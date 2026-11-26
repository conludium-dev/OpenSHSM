"""Delay existing bounded movie observations only; retain texture O2, all guest source and runtime semantics."""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-movie-late'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-texture-o2/build.json'
parent = json.loads(parent_path.read_text())
component_path = root / 'window-texture-o2/component-verification.json'
component = json.loads(component_path.read_text())
assert component['result'] == 'TEXTURE_O2_REAL_GL_PIXELS172_EVICTION1600_EQUAL'
assert component['buildSha256'] == sha(parent_path)
for path, digest in {**parent['dependencies'], **parent['retainedInputs']}.items():
    assert sha(Path(path)) == digest
temporary = Path(tempfile.mkdtemp(prefix='openshsm-movie-late-', dir='/private/tmp'))
probe = temporary / 'gate-probe'
arguments = json.loads((root / 'window-fp-guard/output_37.cpp.record.json').read_text())['arguments']
sdk = arguments[arguments.index('-isysroot') + 1]
command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-isysroot', sdk, '-std=c++17', '-O2',
    str(public / 'stock_movie_capture_gate_probe.cpp'), '-o', str(probe)]
result = subprocess.run(command, capture_output=True, text=True, timeout=30)
assert result.returncode == 0, result.stderr
result = subprocess.run([str(probe)], capture_output=True, text=True, timeout=5)
assert result.returncode == 0 and 'MOVIE_CAPTURE_DELAY_BOUNDARY_INVALID_CLOCK_PASS' in result.stdout
gate_probe = {'result': result.stdout.strip(), 'returncode': result.returncode,
    'executablePath': str(probe), 'executableSha256': sha(probe), 'compileCommand': command}

original_header = root / 'window-movie-input/stock_movie_timing.h'
patches = [('#include "stock_movie_input.h"', '#include "stock_movie_input.h"\n#include "stock_movie_capture_gate.h"'),
    ('    stock_movie_input::observe(ctx, site, serial);', '''    static stock_movie_capture_gate::Gate gate(std::getenv("NWII_MOVIE_CAPTURE_AFTER_MS"));
    if (!gate.valid) {
        return;
    }
    if (gate.delay_us) {
        const auto gate_now = std::chrono::steady_clock::now().time_since_epoch();
        const auto gate_us = std::chrono::duration_cast<std::chrono::microseconds>(gate_now).count();
        if (gate_us < 0 || !gate.accept(static_cast<uint64_t>(gate_us))) {
            return;
        }
    }
    stock_movie_input::observe(ctx, site, serial);''')]
header = original_header.read_text()
for before, after in patches:
    assert header.count(before) == 1
    header = header.replace(before, after, 1)
(output / 'stock_movie_timing.h').write_text(header)
for source in [public / 'stock_movie_capture_gate.h', public / 'stock_movie_input.h',
    root / 'window-movie-input/constant_fp_guard.h']:
    (output / source.name).write_bytes(source.read_bytes())
old_input = json.loads((root / 'window-movie-input/build.json').read_text())
command = list(parent['linkCommand'])
changes = {}
for unit in (11, 37):
    old = next(Path(arg) for arg in command if Path(arg).name == f'output_{unit}.cpp.o')
    original = old.with_suffix('')
    source, obj = output / original.name, output / old.name
    source.write_bytes(original.read_bytes())
    arguments = old_input['changes'][str(unit)]['arguments']
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
        '-I', str(original.parent), '-I', str(root / 'headless-psq-scale'), '-I', str(root / 'window-movie-dma'),
        '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
    (output / f'compile-{unit}.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-2500:]
    command[command.index(str(old))] = str(obj)
    changes[str(unit)] = {'originalPath': str(original), 'originalSha256': sha(original),
        'sourceSha256': sha(source), 'objectSha256': sha(obj), 'arguments': arguments}
exe = temporary / 'OpenSHSMStockMovieLate'
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2500:]
retained = {}
for arg in command:
    if Path(arg).suffix in ('.o', '.a') and arg not in [str(output / f'output_{unit}.cpp.o') for unit in (11, 37)]:
        path = (Path(arg) if Path(arg).is_absolute() else root / 'export/build' / arg).resolve()
        retained[str(path)] = sha(path)
restored = header
for before, after in reversed(patches):
    assert restored.count(after) == 1
    restored = restored.replace(after, before, 1)
assert restored == original_header.read_text()
(output / 'build.json').write_text(json.dumps({
    'result': 'DELAYED_MOVIE_OBSERVER_BUILT_FRAME_LIVE_UNVERIFIED',
    'parentBuildSha256': sha(parent_path), 'parentComponentSha256': sha(component_path),
    'headerOriginalPath': str(original_header), 'headerPatches': patches, 'changes': changes,
    'executablePath': str(exe), 'executableSha256': sha(exe), 'linkCommand': command,
    'retainedInputs': retained, 'gateProbe': gate_probe,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(),
        public / 'stock_movie_capture_gate.h', public / 'stock_movie_capture_gate_probe.cpp',
        original_header, output / 'stock_movie_timing.h', output / 'stock_movie_input.h', output / 'constant_fp_guard.h']},
    'limits': ['Only observer time gate; unchanged guest sources/unit11+37, other73/master/main/runtime/audio/clock retained.',
        'Delay measured from first observed movie boundary, not process start or game time.',
        'Default unset/zero reproduces original observer; invalid decimal/range fails closed.',
        'Existing128 packet/16MiB input and4096 event caps remain; delayed opening can begin inside a frame.',
        'Gate native component passes; full frame/late caller/live verification pending, no runner gate/promotion.']}, indent=2) + '\n')
print('DELAYED_MOVIE_OBSERVER_BUILT_FRAME_LIVE_UNVERIFIED', exe)

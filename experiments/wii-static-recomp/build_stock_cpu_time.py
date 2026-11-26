"""Extend the existing movie boundary recorder with supported host thread CPU time, not decoder replacement."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-cpu-time'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-decoder-o3/build.json'
parent = json.loads(parent_path.read_text())
for path, digest in {**parent['dependencies'], **parent['retainedInputs']}.items():
    assert sha(Path(path)) == digest
original_header = public / 'stock_movie_timing.h'
header = output / 'stock_movie_timing.h'
patches = [('#include <cstdlib>', '#include <cstdlib>\n#include <time.h>'),
    ('    const auto now = std::chrono::steady_clock::now().time_since_epoch();',
     '    timespec cpu_time{};\n'
     '    const int cpu_result = clock_gettime(CLOCK_THREAD_CPUTIME_ID, &cpu_time);\n'
     '    const long long cpu_us = cpu_result == 0 ? (long long)cpu_time.tv_sec * 1000000 + cpu_time.tv_nsec / 1000 : -1;\n'
     '    const auto now = std::chrono::steady_clock::now().time_since_epoch();'),
    ('\\"hostUs\\":%lld,\\"site\\":%u', '\\"hostUs\\":%lld,\\"hostThreadCpuUs\\":%lld,\\"site\\":%u'),
    ('serial++, static_cast<long long>(us), site,', 'serial++, static_cast<long long>(us), cpu_us, site,')]
text = original_header.read_text()
for before, after in patches:
    assert text.count(before) == 1
    text = text.replace(before, after)
header.write_text(text)
guard = output / 'constant_fp_guard.h'
guard.write_bytes((root / 'window-decoder-o3/constant_fp_guard.h').read_bytes())
command = list(parent['linkCommand'])
full = json.loads((root / 'window-quantization/build.json').read_text())['compiled']
changes = {}
for unit in (11, 37):
    old = next(Path(arg) for arg in command if Path(arg).name == f'output_{unit}.cpp.o')
    original = old.with_suffix('')
    source, obj = output / original.name, output / old.name
    source.write_bytes(original.read_bytes())
    arguments = (parent['arguments'] if unit == 37 else
        next(row['arguments'] for row in full if row['source'] == original.name))
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
        '-I', str(original.parent), '-I', str(root / 'headless-psq-scale'),
        '-I', str(root / 'window-movie-dma'), '-c', str(source), '-o', str(obj)],
        capture_output=True, text=True, timeout=180)
    (output / f'compile-{unit}.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-2500:]
    command[command.index(str(old))] = str(obj)
    changes[str(unit)] = {'originalPath': str(original), 'originalSha256': sha(original),
        'sourceSha256': sha(source), 'objectSha256': sha(obj), 'arguments': arguments}
exe = output / 'OpenSHSMStockCPUTime'
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2500:]
inputs = {}
for arg in command:
    if Path(arg).suffix in ('.o', '.a') and arg not in [str(output / f'output_{unit}.cpp.o') for unit in (11, 37)]:
        path = (Path(arg) if Path(arg).is_absolute() else root / 'export/build' / arg).resolve()
        inputs[str(path)] = sha(path)
(output / 'build.json').write_text(json.dumps({'result': 'EXISTING_MOVIE_THREAD_CPU_TIME_BUILT_LIVE_UNVERIFIED',
    'parentBuildSha256': sha(parent_path), 'changes': changes, 'headerPatches': patches,
    'linkCommand': command, 'executableSha256': sha(exe), 'retainedInputs': inputs,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), original_header, header, guard]},
    'limits': ['Two already-observed units recompiled with identical source, only observer header extended.',
        'Mac-only diagnostic CLOCK_THREAD_CPUTIME_ID; kernel+user CPU time on the one emulator host thread.',
        'Boundary deltas include other guest threads/IRQs; NOT pure original decoder-exclusive CPU cost.',
        'CPU clock unavailable is -1, not zero/success; no game/clock/renderer/audio/guest behavior changed.']}, indent=2) + '\n')
print('EXISTING_MOVIE_THREAD_CPU_TIME_BUILT_LIVE_UNVERIFIED')

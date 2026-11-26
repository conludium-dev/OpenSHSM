"""Compare real generated-shader pixels before/after a future BP write on both parsers."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--build', type=Path, required=True)
args = parser.parse_args()
build_path = args.build.resolve()
assert build_path.parent.parent == Path('/private/tmp') and build_path.parent.name.startswith('openshsm-bp-parse-order-')
project = Path(__file__).resolve().parents[2]
root = project / 'work/private-game/static-recomp/stock-baseline'
public = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
build = json.loads(build_path.read_text())
parent_path = root / 'window-context-stage/build.json'
parent = json.loads(parent_path.read_text())
assert build['parentBuildSha256'] == sha(parent_path)
assert sha(build['archivePath']) == build['archiveSha256']
assert sha(parent['archivePath']) == parent['archiveSha256']
cache = Path(tempfile.mkdtemp(prefix='openshsm-bp-order-gpu-', dir='/private/tmp'))
probe = public / 'stock_bp_parse_order_gpu.cpp'
obj = cache / 'probe.cpp.o'
flags_path = root / 'window-movie-late/build.json'
flags = json.loads(flags_path.read_text())['changes']['37']['arguments']
command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-I', str(root / 'headless-tev-banks/include'),
    *flags, '-UNDEBUG', '-c', str(probe), '-o', str(obj)]
compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
assert compiled.returncode == 0, compiled.stderr[-3000:]
results = []
for ordered, record in [(False, parent), (True, build)]:
    link = list(record['linkCommand'])
    main = next(arg for arg in link if Path(arg).name == 'main.cpp.o')
    link[link.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
    link.insert(1, str(obj))
    exe = cache / ('ordered' if ordered else 'baseline')
    link[link.index('-o') + 1] = str(exe)
    linked = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
    assert linked.returncode == 0, linked.stderr[-3000:]
    env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
    run = subprocess.run([str(exe), str(int(ordered))], env=env, capture_output=True, text=True, timeout=30)
    assert run.returncode == 0 and 'BP_REAL_GPU' in run.stdout, run.stdout + run.stderr
    results.append({'ordered': ordered, 'executablePath': str(exe), 'executableSha256': sha(exe),
        'linkCommand': link, 'stdout': run.stdout, 'stderr': run.stderr})
report = {'result': 'BP_PARSE_ORDER_REAL_GPU_BASELINE_LEAK_CANDIDATE_ORDERED_PASS',
    'buildSha256': sha(build_path), 'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(),
        probe, parent_path, flags_path]}, 'compileCommand': command, 'runs': results,
    'limits': ['Actual generated fragment shader on real GL, custom full-screen vertex shader and synthetic KONST state.',
        'Not complete GX renderer batching/FIFO/presentation or original Wii/SHSM textured scene acceptance.',
        'No menu/band-cause/live performance/audio/decoder ownership proof or default promotion.']}
path = cache / 'verification.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
print(json.dumps(results, indent=2))

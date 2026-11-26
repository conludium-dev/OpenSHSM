"""Verify actual candidate parser ordering, masked/split writes and cached display lists."""
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
assert build['result'] == 'BP_PARSE_ORDER_BUILT_UNVERIFIED'
assert all(sha(path) == value for path, value in {**build['dependencies'], **build['retainedInputs']}.items())
assert sha(build['archivePath']) == build['archiveSha256']
assert sha(build['sourcePath']) == build['sourceSha256']
assert hashlib.sha256(subprocess.check_output(['/usr/bin/ar', '-p', build['archivePath'], 'fifo_parser.cpp.o'])).hexdigest() == build['objectSha256']
text = Path(build['sourcePath']).read_text()
for before, after in reversed(build['patches']):
    assert text.count(after) == 1
    text = text.replace(after, before, 1)
assert text == Path(build['originalSourcePath']).read_text()
cache = Path(tempfile.mkdtemp(prefix='openshsm-bp-order-tests-', dir='/private/tmp'))
probe = public / 'stock_bp_parse_order_probe.cpp'
obj = cache / 'probe.cpp.o'
flags_path = root / 'window-movie-late/build.json'
flags = json.loads(flags_path.read_text())['changes']['37']['arguments']
command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-I', str(root / 'headless-tev-banks/include'),
    *flags, '-UNDEBUG', '-c', str(probe), '-o', str(obj)]
compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
assert compiled.returncode == 0, compiled.stderr[-3000:]
link = list(build['linkCommand'])
main = next(arg for arg in link if Path(arg).name == 'main.cpp.o')
link[link.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
link.insert(1, str(obj))
exe = cache / 'bp-order-probe'
link[link.index('-o') + 1] = str(exe)
linked = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert linked.returncode == 0, linked.stderr[-3000:]
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
run = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=30)
assert run.returncode == 0 and 'BP_ORDER_DIRECT8_MASK8_SPLIT8_APPLY24_INITIAL1_DL4_KONST8_PASS' in run.stdout, run.stdout + run.stderr
report = {'result': 'BP_PARSE_ORDER_ACTUAL_NATIVE_DIRECT_MASK_SPLIT_DL_KONST_PASS',
    'buildSha256': sha(build_path), 'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), probe, flags_path]},
    'compileCommand': command, 'linkCommand': link, 'executablePath': str(exe), 'executableSha256': sha(exe),
    'stdout': run.stdout, 'stderr': run.stderr,
    'limits': ['Actual linked candidate parser/generator; synthetic RAM/commands, not original Wii/SHSM stream.',
        'No real GPU draw, live menu, timing, texture ownership, audio or performance verification yet.']}
path = cache / 'verification.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)

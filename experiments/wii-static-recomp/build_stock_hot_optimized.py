"""Optimize measured texture-conversion batch without replacing source or changing runtime behavior."""
from pathlib import Path
import hashlib
import json
import re
import shlex
import subprocess
import time

project = Path('.').resolve()
root = project / 'work/private-game/static-recomp/stock-baseline'
build = root / 'export/build'
output = root / 'window-hot-o2'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
source = root / 'export/output_47.cpp'
source_hash = sha(source)
flags = (build / 'CMakeFiles/OpenSHSMStockBaseline.dir/flags.make').read_text()
compiler = re.search(r'# compile CXX with (.+)', flags)[1]
arguments = []
for name in ('CXX_DEFINES', 'CXX_INCLUDES', 'CXX_FLAGS'):
    arguments += shlex.split(re.search(r'^' + name + r' = (.*)$', flags, re.M)[1])
assert not any('NDEBUG' in item or 'fast-math' in item for item in arguments)
options = ['-O2', '-fno-strict-aliasing', '-fwrapv', '-ffp-contract=off']
obj = output / 'output_47.cpp.o'
depfile = output / 'output_47.d'
start = time.monotonic()
print('Compiling unchanged110779-line batch47 with O2; assertions/guards retained', flush=True)
result = subprocess.run([compiler, *arguments, *options, '-MMD', '-MF', str(depfile), '-c', str(source), '-o', str(obj)],
    capture_output=True, text=True, timeout=600)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
assert sha(source) == source_hash
archive = root / 'ipc-cpbp/libnwiiruntime.a'
runtime_manifest = json.loads((root / 'ipc-cpbp/build.json').read_text())
assert sha(archive) == runtime_manifest['archiveSha256']
entry = root / 'window-paced/main.cpp.o'
entry_source = root / 'window-paced/main.cpp'
entry_manifest = json.loads((root / 'window-paced/build.json').read_text())
assert sha(entry_source) == entry_manifest['sourceSha256']
command = shlex.split((build / 'CMakeFiles/OpenSHSMStockBaseline.dir/link.txt').read_text())
old_entry = 'CMakeFiles/OpenSHSMStockBaseline.dir/nWiiRuntime/src/core/main.cpp.o'
old_batch = 'CMakeFiles/OpenSHSMStockBaseline.dir/output_47.cpp.o'
assert command.count(old_entry) == command.count(old_batch) == 1
retained = {item: sha(build / item) for item in command if item.endswith('.cpp.o') and item not in (old_entry, old_batch)}
command[command.index(old_entry)] = str(entry)
command[command.index(old_batch)] = str(obj)
command[command.index('nWiiRuntime/libnwiiruntime.a')] = str(archive)
exe = output / 'OpenSHSMStockHotO2'
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=build, capture_output=True, text=True, timeout=120)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
dependencies = shlex.split(depfile.read_text().replace('\\\n', '').split(':', 1)[1])
(output / 'build.json').write_text(json.dumps({
    'result': 'HOT_BATCH_O2_BUILT_EXECUTION_PENDING', 'compileSeconds': time.monotonic() - start,
    'compilerOptions': options, 'sourceSha256': source_hash, 'objectSha256': sha(obj),
    'entrySha256': sha(entry), 'entrySourceSha256': sha(entry_source),
    'archiveSha256': sha(archive), 'executableSha256': sha(exe),
    'retainedObjects': retained, 'dependencies': {name: sha(Path(name)) for name in dependencies},
    'limits': ['One complete generated batch optimized, not full runtime or all guest code.',
        'No source/header replacements, NDEBUG, fast-math, guest bypass or timing/state changes.',
        'Need actual startup/render comparison; optimization does not prove original behavior equivalence.']
}, indent=2) + '\n')
print('Built hot O2 batch;', len(retained), 'other guest/dispatcher objects, paced entry and whole runtime retained')

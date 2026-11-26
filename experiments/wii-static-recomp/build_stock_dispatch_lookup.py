"""Keep setjmp wrapper unoptimized; replace only exact function-address routing."""
from pathlib import Path
import hashlib
import json
import re
import shlex
import subprocess
from stock_dispatch_patch import adapt_dispatch

project = Path('.').resolve()
root = project / 'work/private-game/static-recomp/stock-baseline'
build = root / 'export/build'
output = root / 'window-lookup'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
original = root / 'export/main_output.cpp'
text, routes = adapt_dispatch(original.read_text())
source = output / 'main_output.cpp'
source.write_text(text)
flags = (build / 'CMakeFiles/OpenSHSMStockBaseline.dir/flags.make').read_text()
compiler = re.search(r'# compile CXX with (.+)', flags)[1]
arguments = []
for name in ('CXX_DEFINES', 'CXX_INCLUDES', 'CXX_FLAGS'):
    arguments += shlex.split(re.search(r'^' + name + r' = (.*)$', flags, re.M)[1])
obj = output / 'main_output.cpp.o'
result = subprocess.run([compiler, *arguments, '-I', str(root / 'export'), '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
command = shlex.split((build / 'CMakeFiles/OpenSHSMStockBaseline.dir/link.txt').read_text())
entry_name = 'CMakeFiles/OpenSHSMStockBaseline.dir/nWiiRuntime/src/core/main.cpp.o'
dispatch_name = 'CMakeFiles/OpenSHSMStockBaseline.dir/main_output.cpp.o'
retained = {name: sha(build / name) for name in command if name.endswith('.cpp.o') and name not in (entry_name, dispatch_name)}
entry = root / 'window-paced/main.cpp.o'
archive = root / 'ipc-cpbp/libnwiiruntime.a'
command[command.index(entry_name)] = str(entry)
command[command.index(dispatch_name)] = str(obj)
command[command.index('nWiiRuntime/libnwiiruntime.a')] = str(archive)
exe = output / 'OpenSHSMStockDispatchLookup'
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=build, capture_output=True, text=True, timeout=120)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
(output / 'build.json').write_text(json.dumps({
    'result': 'EXACT_DISPATCH_LOOKUP_BUILT_EXECUTION_PENDING', 'routes': len(routes),
    'baseSourceSha256': sha(original), 'sourceSha256': sha(source),
    'executableSha256': sha(exe), 'entrySha256': sha(entry), 'archiveSha256': sha(archive),
    'retainedObjects': retained,
    'limits': ['Existing dispatcher exact switch converted to sorted address table, no new runtime registry.',
        'O0/setjmp, context/IRQ handling, bounds fallback/interpreter and all75 guest batches unchanged.',
        'Need mapping and full startup/render verification; no performance claim yet.']
}, indent=2) + '\n')
print('Built exact lookup;', len(routes), 'routes;', len(retained), 'guest batches retained')

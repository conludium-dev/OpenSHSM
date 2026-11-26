"""Compile one observed guest module against the unchanged full DrawDone baseline."""
from pathlib import Path
import hashlib
import json
import re
import shlex
import subprocess
from stock_vi_path_observation import adapt_vi_path

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
build = root / 'export/build'
output = root / 'window-vi-path'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base = root / 'window-optimized/output_39.cpp'
source = output / 'output_39.cpp'
text, stages, calls = adapt_vi_path(base.read_text())
source.write_text(text)
flags = (build / 'CMakeFiles/OpenSHSMStockBaseline.dir/flags.make').read_text()
compiler = re.search(r'# compile CXX with (.+)', flags)[1]
arguments = []
for name in ('CXX_DEFINES', 'CXX_INCLUDES', 'CXX_FLAGS'):
    arguments += shlex.split(re.search(r'^' + name + r' = (.*)$', flags, re.M)[1])
arguments += ['-I', str(root / 'export'), '-O2', '-fno-strict-aliasing', '-fwrapv', '-ffp-contract=off']
obj = output / 'output_39.cpp.o'
result = subprocess.run([compiler, *arguments, '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
command = shlex.split((build / 'CMakeFiles/OpenSHSMStockBaseline.dir/link.txt').read_text())
for i in range(75):
    command[command.index(f'CMakeFiles/OpenSHSMStockBaseline.dir/output_{i}.cpp.o')] = str(obj if i == 39 else root / 'window-optimized' / f'output_{i}.cpp.o')
command[command.index('CMakeFiles/OpenSHSMStockBaseline.dir/nWiiRuntime/src/core/main.cpp.o')] = str(root / 'window-paced/main.cpp.o')
command[command.index('CMakeFiles/OpenSHSMStockBaseline.dir/main_output.cpp.o')] = str(root / 'window-lookup/main_output.cpp.o')
archive = root / 'window-draw-done/libnwiiruntime.a'
command[command.index('nWiiRuntime/libnwiiruntime.a')] = str(archive)
exe = output / 'OpenSHSMStockVIPath'
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=build, capture_output=True, text=True, timeout=120)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
(output / 'build.json').write_text(json.dumps({
    'result': 'READ_ONLY_VI_PATH_BUILT', 'baseSourceSha256': sha(base), 'sourceSha256': sha(source),
    'objectSha256': sha(obj), 'archiveSha256': sha(archive), 'executableSha256': sha(exe),
    'stages': [hex(address) for address in stages], 'observedCallReturnChecks': calls,
    'retainedObjects': {item: sha(Path(item) if Path(item).is_absolute() else build / item)
        for item in command if item.endswith('.cpp.o') and item != str(obj)},
    'limits': ['Only read-only guest instrumentation; every32nd stage hit, 30000 records maximum.',
        'Original opcode statements/branches preserved; diagnostic timing can differ, not original dynamic Wii oracle.']
}, indent=2) + '\n')
print('Built VI path observer; one guest module instrumented, full runtime and other76 objects retained', flush=True)

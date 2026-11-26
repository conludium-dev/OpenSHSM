"""Build one corrected parser object on the existing full transport/IRQ runtime."""
from pathlib import Path
import hashlib
import json
import re
import shlex
import shutil
import subprocess
from stock_draw_done_patch import adapt_draw_done

project = Path('.').resolve()
root = project / 'work/private-game/static-recomp/stock-baseline'
build = root / 'export/build'
output = root / 'window-draw-done'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
flags = (build / 'nWiiRuntime/CMakeFiles/nwiiruntime.dir/flags.make').read_text()
compiler = re.search(r'# compile CXX with (.+)', flags)[1]
arguments = []
for name in ('CXX_DEFINES', 'CXX_INCLUDES', 'CXX_FLAGS'):
    arguments += shlex.split(re.search(r'^' + name + r' = (.*)$', flags, re.M)[1])
base_source = root / 'export/nWiiRuntime/src/hle/gx/fifo_parser.cpp'
source = output / 'fifo_parser.cpp'
source.write_text(adapt_draw_done(base_source.read_text()))
obj = output / 'fifo_parser.cpp.o'
subprocess.run([compiler, *arguments, '-c', str(source), '-o', str(obj)], check=True, capture_output=True, timeout=120)
base_archive = root / 'window-transport-irq-order/libnwiiruntime.a'
archive = output / 'libnwiiruntime.a'
shutil.copy2(base_archive, archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], check=True, capture_output=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
retained = {}
for member in subprocess.check_output(['/usr/bin/ar', '-t', str(base_archive)], text=True).splitlines():
    if member == obj.name or member.startswith('__.SYMDEF'):
        continue
    old = subprocess.check_output(['/usr/bin/ar', '-p', str(base_archive), member])
    assert old == subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member]), member
    retained[member] = hashlib.sha256(old).hexdigest()
command = shlex.split((build / 'CMakeFiles/OpenSHSMStockBaseline.dir/link.txt').read_text())
for i in range(75):
    command[command.index(f'CMakeFiles/OpenSHSMStockBaseline.dir/output_{i}.cpp.o')] = str(root / 'window-optimized' / f'output_{i}.cpp.o')
entry_name = 'CMakeFiles/OpenSHSMStockBaseline.dir/nWiiRuntime/src/core/main.cpp.o'
command[command.index(entry_name)] = str(root / 'window-paced/main.cpp.o')
command[command.index('CMakeFiles/OpenSHSMStockBaseline.dir/main_output.cpp.o')] = str(root / 'window-lookup/main_output.cpp.o')
command[command.index('nWiiRuntime/libnwiiruntime.a')] = str(archive)
exe = output / 'OpenSHSMStockDrawDone'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=build, check=True, capture_output=True, timeout=120)
contract_obj = output / 'contract.cpp.o'
subprocess.run([compiler, *arguments, '-c', str(project / 'experiments/wii-static-recomp/stock_draw_done_contract.cpp'), '-o', str(contract_obj)], check=True, capture_output=True, timeout=60)
test_command = list(command)
test_command[test_command.index(str(root / 'window-paced/main.cpp.o'))] = str(root / 'window-cp-transport/contract-entry.cpp.o')
test_command.insert(1, str(contract_obj))
probe = output / 'draw-done-contract'
test_command[test_command.index('-o') + 1] = str(probe)
subprocess.run(test_command, cwd=build, check=True, capture_output=True, timeout=120)
result = subprocess.run([str(probe)], check=True, capture_output=True, text=True, timeout=20)
(output / 'contract.log').write_text(result.stdout + result.stderr)
(output / 'build.json').write_text(json.dumps({
    'result': 'DRAW_DONE_DISTINCT_FROM_COPY_BUILT', 'sourceSha256': sha(source), 'baseSourceSha256': sha(base_source),
    'objectSha256': sha(obj), 'executableSha256': sha(exe), 'archiveSha256': sha(archive),
    'retainedRuntimeMembers': retained,
    'retainedObjects': {item: sha(Path(item) if Path(item).is_absolute() else build / item) for item in command if item.endswith('.cpp.o')},
    'contract': result.stdout.strip(),
    'limits': ['Actual parser/apply contract; not original dynamic GPU timing or visual/menu acceptance.',
        'Real BP45 finish remains at parse time; CPU handoff, races and renderer completion remain unverified.']
}, indent=2) + '\n')
print(result.stdout.strip(), flush=True)

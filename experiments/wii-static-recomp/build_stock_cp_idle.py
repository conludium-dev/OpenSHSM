"""Build two host idle-status objects atop the immutable optimized guest baseline."""
from pathlib import Path
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import argparse
from stock_cp_idle_patch import adapt_cp_idle, adapt_gx_idle
from stock_cp_transport_patch import adapt_cp_transport, adapt_gx_transport, adapt_pi_transport

parser = argparse.ArgumentParser()
parser.add_argument('--transport', action='store_true')
args = parser.parse_args()

project = Path('.').resolve()
root = project / 'work/private-game/static-recomp/stock-baseline'
build = root / 'export/build'
output = root / ('window-cp-transport' if args.transport else 'window-cp-idle')
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
flags = (build / 'nWiiRuntime/CMakeFiles/nwiiruntime.dir/flags.make').read_text()
compiler = re.search(r'# compile CXX with (.+)', flags)[1]
arguments = []
for name in ('CXX_DEFINES', 'CXX_INCLUDES', 'CXX_FLAGS'):
    arguments += shlex.split(re.search(r'^' + name + r' = (.*)$', flags, re.M)[1])
objects = []
sources = {}
inputs = [(root / 'ipc-cpbp/hw_cp.cpp', adapt_cp_idle), (root / 'export/nWiiRuntime/src/hle/gx.cpp', adapt_gx_idle)]
if args.transport:
    inputs.append((root / 'export/nWiiRuntime/src/hw/hw_pi.cpp', adapt_pi_transport))
for original, adapter in inputs:
    source = output / original.name
    text = adapter(original.read_text())
    if args.transport and original.name != 'hw_pi.cpp':
        text = (adapt_cp_transport if original.name == 'hw_cp.cpp' else adapt_gx_transport)(text)
    source.write_text(text)
    obj = output / (source.name + '.o')
    result = subprocess.run([compiler, *arguments, '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=120)
    (output / (source.stem + '-compile.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-3000:]
    objects.append(obj)
    sources[source.name] = {'baseSha256': sha(original), 'sourceSha256': sha(source), 'objectSha256': sha(obj)}
base_archive = root / 'ipc-cpbp/libnwiiruntime.a'
archive = output / 'libnwiiruntime.a'
shutil.copy2(base_archive, archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), *map(str, objects)], check=True, capture_output=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
retained = {}
for member in subprocess.check_output(['/usr/bin/ar', '-t', str(base_archive)], text=True).splitlines():
    if member in {item.name for item in objects} or member.startswith('__.SYMDEF'):
        continue
    old = subprocess.check_output(['/usr/bin/ar', '-p', str(base_archive), member])
    new = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    assert old == new, member
    retained[member] = hashlib.sha256(old).hexdigest()
command = shlex.split((build / 'CMakeFiles/OpenSHSMStockBaseline.dir/link.txt').read_text())
for i in range(75):
    name = f'CMakeFiles/OpenSHSMStockBaseline.dir/output_{i}.cpp.o'
    command[command.index(name)] = str(root / 'window-optimized' / f'output_{i}.cpp.o')
entry_name = 'CMakeFiles/OpenSHSMStockBaseline.dir/nWiiRuntime/src/core/main.cpp.o'
command[command.index(entry_name)] = str(root / 'window-paced/main.cpp.o')
dispatch_name = 'CMakeFiles/OpenSHSMStockBaseline.dir/main_output.cpp.o'
command[command.index(dispatch_name)] = str(root / 'window-lookup/main_output.cpp.o')
command[command.index('nWiiRuntime/libnwiiruntime.a')] = str(archive)
exe = output / ('OpenSHSMStockCPTransport' if args.transport else 'OpenSHSMStockCPIdle')
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=build, capture_output=True, text=True, timeout=120)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
entry = output / 'contract-entry.cpp.o'
subprocess.run([compiler, *arguments, '-I', str(root / 'export/nWiiRuntime/src'), '-Dmain=shsm_unused_boot_main', '-c', str(root / 'window-paced/main.cpp'), '-o', str(entry)], check=True, timeout=120)
contract = output / 'contract.cpp.o'
recipe = project / 'experiments/wii-static-recomp' / ('stock_cp_transport_contract.cpp' if args.transport else 'stock_cp_idle_contract.cpp')
subprocess.run([compiler, *arguments, '-c', str(recipe), '-o', str(contract)], check=True, timeout=60)
test_command = list(command)
test_command[test_command.index(str(root / 'window-paced/main.cpp.o'))] = str(entry)
test_command.insert(1, str(contract))
probe = output / 'cp-idle-contract'
test_command[test_command.index('-o') + 1] = str(probe)
subprocess.run(test_command, cwd=build, check=True, capture_output=True, timeout=120)
result = subprocess.run([str(probe)], capture_output=True, text=True, timeout=20)
(output / 'contract.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stdout + result.stderr
(output / 'build.json').write_text(json.dumps({
    'result': 'CP_TRANSPORT_BUILT' if args.transport else 'CP_IDLE_QUEUE_STATUS_BUILT', 'sources': sources,
    'transportEnabled': args.transport,
    'archiveSha256': sha(archive), 'executableSha256': sha(exe),
    'retainedRuntimeMembers': retained,
    'retainedObjects': {item: sha(Path(item) if Path(item).is_absolute() else build / item)
        for item in command if item.endswith('.cpp.o')},
    'contract': result.stdout.strip(),
    'limits': ['Dolphin-reference CP register predicates + PC-adapter existing host WGP/decoder queue visibility.',
        'Atomic decode-byte mirror reflects existing parser buffer; rendering carry is not CP decoding.',
        'Actual runtime objects/MMIO/WGP/parser exercised with no guest boot/resources/render/window; not live Wii timing.',
        ('Actual 32-byte RAM publication, linked CP distance, inclusive-end wrap and decoder acknowledgement tested in MEM1/MEM2; no cycle-exact or full watermark/backpressure claim.'
         if args.transport else 'Existing FIFO pointers/link/MEM2 and parser overflow guard remain incomplete; no new token/ready/callback writes.'),
        'No forced guest token/ready/callback or watchdog changes; full boot acceptance is separate.']
}, indent=2) + '\n')
print(result.stdout.strip().splitlines()[-1], flush=True)

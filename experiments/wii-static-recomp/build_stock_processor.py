"""Integrate the existing processor adapter without changing the CPUContext ABI."""
from pathlib import Path
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import argparse
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--division-contract', action='store_true')
parser.add_argument('--carry', action='store_true')
parser.add_argument('--carry-isa-contract', action='store_true')
parser.add_argument('--locked-cache', action='store_true')
parser.add_argument('--quantization', action='store_true')
args = parser.parse_args()
assert not args.carry_isa_contract or args.carry
assert not (args.division_contract and args.carry_isa_contract)
assert not args.locked_cache or (args.carry and (args.division_contract or args.carry_isa_contract))
assert not args.quantization or args.locked_cache

project = Path('.').resolve()
root = project / 'work/private-game/static-recomp/stock-baseline'
build = root / 'export/build'
output = root / ('window-hid2-carry' if args.carry else 'window-hid2')
exe_name = 'OpenSHSMStockHID2Carry' if args.carry else 'OpenSHSMStockHID2'
if args.locked_cache:
    output = root / 'window-locked-cache'
    exe_name = 'OpenSHSMStockLockedCache'
if args.quantization:
    output = root / 'window-quantization'
    exe_name = 'OpenSHSMStockQuantization'
experiment = project / 'experiments/wii-static-recomp'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
lowering = json.loads(((root / 'window-hid2-carry' if args.locked_cache else output) / 'lowering.json').read_text())
assert lowering['adapterHeaderSha256'] == sha(experiment / 'processor_adapter.h')
assert lowering['adapterSourceSha256'] == sha(experiment / 'processor_adapter.cpp')
flags = (build / 'nWiiRuntime/CMakeFiles/nwiiruntime.dir/flags.make').read_text()
compiler = re.search(r'# compile CXX with (.+)', flags)[1]
arguments = []
for name in ('CXX_DEFINES', 'CXX_INCLUDES', 'CXX_FLAGS'):
    arguments += shlex.split(re.search(r'^' + name + r' = (.*)$', flags, re.M)[1])
arguments += ['-I', str(experiment), '-I', str(root / 'export'), '-I', str(root / 'export/nWiiRuntime/src')]
if args.carry:
    arguments = ['-I', str(output), *arguments]
if args.locked_cache:
    arguments = ['-I', str(output / 'include'), *arguments]
if args.division_contract or args.carry_isa_contract:
    current = json.loads((output / 'build.json').read_text())
    assert sha(output / exe_name) == current['executableSha256']
    probe_name = 'carry-isa-probe' if args.carry_isa_contract else 'division-probe'
    contract_source = experiment / ('carry_probe.cpp' if args.carry_isa_contract else 'stock_division_probe.cpp')
    recipe_source = contract_source
    if args.carry_isa_contract:
        text = contract_source.read_text()
        marker = '#define main unused_frontend_main\n#include "memory_frontend_probe.cpp"\n#undef main'
        assert text.count(marker) == 1
        contract_source = output / 'carry-isa-probe.cpp'
        contract_source.write_text(text.replace(marker, '#include <iostream>'))
    obj = output / (probe_name + '.cpp.o')
    subprocess.run([compiler, *arguments, '-c', str(contract_source), '-o', str(obj)], check=True, capture_output=True, timeout=60)
    command = shlex.split((build / 'CMakeFiles/OpenSHSMStockBaseline.dir/link.txt').read_text())
    changed = {item['file'] for item in lowering['files']}
    for index in range(75):
        name = f'output_{index}.cpp'
        command[command.index(f'CMakeFiles/OpenSHSMStockBaseline.dir/{name}.o')] = str((output if name in changed or args.locked_cache else root / 'window-optimized') / (name + '.o'))
    command[command.index('CMakeFiles/OpenSHSMStockBaseline.dir/main_output.cpp.o')] = str((output if args.locked_cache else root / 'window-lookup') / 'main_output.cpp.o')
    command[command.index('CMakeFiles/OpenSHSMStockBaseline.dir/nWiiRuntime/src/core/main.cpp.o')] = str(output / 'contract-entry.cpp.o')
    command[command.index('nWiiRuntime/libnwiiruntime.a')] = str(output / 'libnwiiruntime.a')
    exe = output / probe_name
    command[command.index('-o') + 1] = str(exe)
    command.insert(1, str(obj))
    result = subprocess.run(command, cwd=build, capture_output=True, text=True, timeout=120)
    (output / (probe_name + '-link.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-4000:]
    (output / ('carry-isa-build.json' if args.carry_isa_contract else 'division-build.json')).write_text(json.dumps({'sourceSha256': sha(recipe_source),
        'compiledSourceSha256': sha(contract_source),
        'objectSha256': sha(obj), 'executableSha256': sha(exe), 'parentBuildSha256': sha(output / 'build.json'),
        'linkCommand': command}, indent=2) + '\n')
    print('Built whole original __div2u probe; no boot/source changes', flush=True)
    sys.exit(0)
sources = {}

def compile_source(name, text, extra=()):
    source = output / name
    source.write_text(text)
    obj = output / (name + '.o')
    result = subprocess.run([compiler, *arguments, *extra, '-c', str(source), '-o', str(obj)],
        capture_output=True, text=True, timeout=180)
    (output / (name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-4000:]
    sources[name] = {'sourceSha256': sha(source), 'objectSha256': sha(obj)}
    return obj

entry_text = (root / 'window-paced/main.cpp').read_text()
needle = 'std::make_unique<nwii::runtime::CPUContext>()'
assert entry_text.count(needle) == 1
entry_text = '#include "processor_adapter.h"\n' + entry_text.replace(needle, 'std::make_unique<nwii::runtime::ProcessorContext>()')
entry = compile_source('main.cpp', entry_text)
adapter = compile_source('processor_adapter.cpp', (experiment / 'processor_adapter.cpp').read_text())
interpreter_text = (root / 'export/nWiiRuntime/src/hle/interpreter.cpp').read_text()
for needle, replacement in (
    ('else if (spr == 27) ctx.gpr[rD] = ctx.srr1;',
     'else if (spr == 27) ctx.gpr[rD] = ctx.srr1;\n            else if (spr == 920) ctx.gpr[rD] = experiment_read_hid2(ctx);'),
    ('else if (spr == 27) ctx.srr1 = ctx.gpr[rD];',
     'else if (spr == 27) ctx.srr1 = ctx.gpr[rD];\n            else if (spr == 920) experiment_write_hid2(ctx, ctx.gpr[rD]);')
):
    assert interpreter_text.count(needle) == 1
    interpreter_text = interpreter_text.replace(needle, replacement)
interpreter = compile_source('interpreter.cpp', '#include "processor_adapter.h"\n' + interpreter_text)
base_archive = root / 'window-draw-done/libnwiiruntime.a'
archive = output / 'libnwiiruntime.a'
shutil.copy2(base_archive, archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(interpreter), str(adapter)], check=True, capture_output=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
retained_runtime = {}
for member in subprocess.check_output(['/usr/bin/ar', '-t', str(base_archive)], text=True).splitlines():
    if member == 'interpreter.cpp.o' or member.startswith('__.SYMDEF'):
        continue
    old = subprocess.check_output(['/usr/bin/ar', '-p', str(base_archive), member])
    assert old == subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member]), member
    retained_runtime[member] = hashlib.sha256(old).hexdigest()
command = shlex.split((build / 'CMakeFiles/OpenSHSMStockBaseline.dir/link.txt').read_text())
changed = {item['file'] for item in lowering['files']}
retained = {}
for index in range(75):
    name = f'output_{index}.cpp'
    obj = (output if name in changed else root / 'window-optimized') / (name + '.o')
    command[command.index(f'CMakeFiles/OpenSHSMStockBaseline.dir/{name}.o')] = str(obj)
    if name not in changed:
        retained[str(obj)] = sha(obj)
dispatcher = root / 'window-lookup/main_output.cpp.o'
command[command.index('CMakeFiles/OpenSHSMStockBaseline.dir/main_output.cpp.o')] = str(dispatcher)
retained[str(dispatcher)] = sha(dispatcher)
command[command.index('CMakeFiles/OpenSHSMStockBaseline.dir/nWiiRuntime/src/core/main.cpp.o')] = str(entry)
command[command.index('nWiiRuntime/libnwiiruntime.a')] = str(archive)
exe = output / exe_name
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=build, capture_output=True, text=True, timeout=120)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-4000:]
contract_entry = compile_source('contract-entry.cpp', entry_text, ['-Dmain=unused_main'])
contract = compile_source('processor-contract.cpp', (experiment / 'stock_processor_contract.cpp').read_text())
test_command = list(command)
test_command[test_command.index(str(entry))] = str(contract_entry)
test_command.insert(1, str(contract))
probe = output / 'processor-contract'
test_command[test_command.index('-o') + 1] = str(probe)
test_link = subprocess.run(test_command, cwd=build, capture_output=True, text=True, timeout=120)
(output / 'contract-link.log').write_text(test_link.stdout + test_link.stderr)
assert test_link.returncode == 0, test_link.stderr[-4000:]
result = subprocess.run([str(probe)], capture_output=True, text=True, timeout=20)
(output / 'contract.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stdout + result.stderr
(output / 'build.json').write_text(json.dumps({
    'result': 'EXISTING_PROCESSOR_ADAPTER_STOCK_INTEGRATED', 'sources': sources,
    'loweringSha256': sha(output / 'lowering.json'), 'retainedObjects': retained,
    'retainedRuntimeMembers': retained_runtime, 'executableSha256': sha(exe),
    'archiveSha256': sha(archive), 'contract': result.stdout.strip(),
    'baseHeaderSha256': sha(root / 'export/nWiiRuntime/include/runtime/cpu_context.h'),
    'limits': ['HID2 register policy and supervisor-mode read/write only; not locked-cache DMA or full CPU fidelity.',
        'Original guest privileged-exception delivery remains unsupported; existing adapter refuses user-mode access.',
        'Actual ProcessorContext allocation is required; base CPUContext ABI is unchanged.',
        'Component contract is not physical Wii, menu, audio, input or full boot acceptance.']
}, indent=2) + '\n')
print(result.stdout.strip(), flush=True)

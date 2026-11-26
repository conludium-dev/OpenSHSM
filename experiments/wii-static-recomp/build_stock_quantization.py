"""Rebuild every existing CPU consumer; no mixed inline PSQ definitions."""
from pathlib import Path
import concurrent.futures
import hashlib
import json
import shlex
import subprocess
from stock_quantization_patch import adapt_quantization
from stock_thp_observation import adapt_thp_calls

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base = root / 'window-locked-cache'
output = root / 'window-quantization'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((base / 'build.json').read_text())
assert sha(base / 'OpenSHSMStockLockedCache') == build['executableSha256']
header = output / 'include/runtime/cpu_context.h'
header.parent.mkdir(parents=True, exist_ok=True)
original_header = base / 'include/runtime/cpu_context.h'
assert sha(original_header) == build['cpuHeaderSha256']
header.write_text(adapt_quantization(original_header.read_text()))
for name in ('processor_adapter.h', 'carry_adapter.h'):
    (output / name).write_bytes((base / name).read_bytes())

def compile_item(item):
    original = base / item['source']
    assert sha(original) == item['sourceSha256']
    source = output / item['source']
    text = original.read_text()
    if source.name == 'os_hle_stubs.cpp':
        text = adapt_thp_calls(text)
    source.write_text(text)
    arguments = [arg.replace(str(base), str(output)) for arg in item['arguments']]
    obj = output / item['object']
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
        '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
    (output / (item['object'] + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-3000:]
    print('Compiled', item['object'], flush=True)
    return {'object': item['object'], 'source': item['source'], 'sourceSha256': sha(source),
        'objectSha256': sha(obj), 'arguments': arguments, 'baseSourceSha256': sha(original)}

assert len(build['compiled']) == 124
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    compiled = list(pool.map(compile_item, build['compiled']))
members = [name for name in subprocess.check_output(['/usr/bin/ar', '-t', str(base / 'libnwiiruntime.a')],
    text=True).splitlines() if not name.startswith('__.SYMDEF')]
assert len(members) == 45
archive = output / 'libnwiiruntime.a'
subprocess.run(['/usr/bin/ar', 'rcs', str(archive), *[str(output / name) for name in members]],
    check=True, capture_output=True)
command = shlex.split((root / 'export/build/CMakeFiles/OpenSHSMStockBaseline.dir/link.txt').read_text())
for index in range(75):
    name = f'output_{index}.cpp.o'
    command[command.index('CMakeFiles/OpenSHSMStockBaseline.dir/' + name)] = str(output / name)
for old, name in [('CMakeFiles/OpenSHSMStockBaseline.dir/main_output.cpp.o', 'main_output.cpp.o'),
    ('CMakeFiles/OpenSHSMStockBaseline.dir/nWiiRuntime/src/core/main.cpp.o', 'main.cpp.o')]:
    command[command.index(old)] = str(output / name)
command[command.index('nWiiRuntime/libnwiiruntime.a')] = str(archive)
exe = output / 'OpenSHSMStockQuantization'
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=120)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
test_command = list(command)
test_command[test_command.index(str(output / 'main.cpp.o'))] = str(output / 'contract-entry.cpp.o')
test_command.insert(1, str(output / 'locked-cache-contract.cpp.o'))
probe = output / 'locked-cache-contract'
test_command[test_command.index('-o') + 1] = str(probe)
result = subprocess.run(test_command, cwd=root / 'export/build', capture_output=True, text=True, timeout=120)
(output / 'contract-link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
result = subprocess.run([str(probe)], capture_output=True, text=True, timeout=20)
(output / 'contract.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stdout + result.stderr
(output / 'build.json').write_text(json.dumps({'result': 'QUANTIZATION_FULL_CONSUMER_REBUILD',
    'baseBuildSha256': sha(base / 'build.json'), 'compiled': compiled, 'runtimeMembers': members,
    'archiveSha256': sha(archive), 'executableSha256': sha(exe), 'linkCommand': command,
    'cpuHeaderSha256': sha(header), 'contractExecutableSha256': sha(probe), 'contract': result.stdout.strip(),
    'limits': ['All124CPU consumers rebuilt; guest program and original media unchanged.',
        'Signed integer quantization corrected; NaN integer stores refused; full FPU/FPSCR/exception semantics unverified.',
        'Read-only THP observer can affect host timing; no readiness/clock/callback forcing.',
        'Component DMA test is not video/menu/audio/controllers acceptance.']}, indent=2) + '\n')
print(result.stdout.strip(), flush=True)

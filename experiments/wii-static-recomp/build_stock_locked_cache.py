"""Rebuild all CPU/MMU consumers with locked-cache backing and actual DMA copies."""
from pathlib import Path
import concurrent.futures
import hashlib
import json
import re
import shlex
import subprocess
from stock_locked_cache_patch import adapt_cpu_header, adapt_processor_header, adapt_interpreter, lower_dma

project = Path('.').resolve()
root = project / 'work/private-game/static-recomp/stock-baseline'
base = root / 'window-hid2-carry'
build = root / 'export/build'
output = root / 'window-locked-cache'
experiment = project / 'experiments/wii-static-recomp'
output.mkdir(exist_ok=True)
headers = output / 'include/runtime'
headers.mkdir(parents=True, exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
dol_path = project / 'work/private-game/disc/DATA/sys/main.dol'
dol = dol_path.read_bytes()
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
cpu_base = root / 'export/nWiiRuntime/include/runtime/cpu_context.h'
(headers / cpu_base.name).write_text(adapt_cpu_header(cpu_base.read_text()))
(output / 'processor_adapter.h').write_text(adapt_processor_header((experiment / 'processor_adapter.h').read_text()))
(output / 'carry_adapter.h').write_bytes((base / 'carry_adapter.h').read_bytes())

def flags(path):
    text = path.read_text()
    compiler = re.search(r'# compile CXX with (.+)', text)[1]
    arguments = ['-I', str(output / 'include'), '-I', str(output), '-I', str(experiment),
        '-I', str(root / 'export'), '-I', str(root / 'export/nWiiRuntime/src')]
    for name in ('CXX_DEFINES', 'CXX_INCLUDES', 'CXX_FLAGS'):
        arguments += shlex.split(re.search(r'^' + name + r' = (.*)$', text, re.M)[1])
    assert not any(flag in arguments for flag in ('-DNDEBUG', '-ffast-math', '-Ofast'))
    return compiler, arguments

compiler, guest_flags = flags(build / 'CMakeFiles/OpenSHSMStockBaseline.dir/flags.make')
runtime_compiler, runtime_flags = flags(build / 'nWiiRuntime/CMakeFiles/nwiiruntime.dir/flags.make')
assert compiler == runtime_compiler
jobs = []
dma_sites = []
for index in range(75):
    name = f'output_{index}.cpp'
    original = (base if (base / name).exists() else root / 'window-optimized') / name
    text, sites = lower_dma(original.read_text(), dol)
    source = output / name
    source.write_text(text)
    dma_sites.extend(dict(site, file=name) for site in sites)
    jobs.append((name + '.o', source, original, guest_flags + ['-O2', '-fno-strict-aliasing', '-fwrapv',
        '-ffp-contract=off', '-include', str(output / 'processor_adapter.h'), '-include', str(output / 'carry_adapter.h')]))
assert {site['spr'] for site in dma_sites} == {922, 923}
raw = (build / 'nWiiRuntime/CMakeFiles/nwiiruntime.dir/build.make').read_text()
mapping = {Path(source).name + '.o': (build / obj, Path(source)) for obj, source in re.findall(
    r'^(nWiiRuntime/[^\n]+?\.(?:cpp|mm)\.o): (/[^\n]+?\.(?:cpp|mm))$', raw, re.M)}
base_archive = base / 'libnwiiruntime.a'
runtime_names = []
for member in subprocess.check_output(['/usr/bin/ar', '-t', str(base_archive)], text=True).splitlines():
    if member.startswith('__.SYMDEF'):
        continue
    digest = hashlib.sha256(subprocess.check_output(['/usr/bin/ar', '-p', str(base_archive), member])).hexdigest()
    obj, original = mapping.get(member, (None, None))
    if obj is None or not obj.exists() or sha(obj) != digest:
        candidates = [path for path in root.glob('*/' + member) if sha(path) == digest and path.with_suffix('').exists()]
        assert candidates, member
        original = candidates[0].with_suffix('')
    source = output / original.name
    text = original.read_text()
    if member == 'interpreter.cpp.o':
        text = adapt_interpreter(text)
    source.write_text(text)
    jobs.append((member, source, original, runtime_flags + ['-I', str(original.parent)]))
    runtime_names.append(member)
adapter = experiment / 'stock_locked_cache_adapter.cpp'
source = output / adapter.name
source.write_bytes(adapter.read_bytes())
jobs.append((adapter.name + '.o', source, adapter, runtime_flags))
runtime_names.append(adapter.name + '.o')
for name, original, extra in (
    ('main.cpp', base / 'main.cpp', []),
    ('main_output.cpp', root / 'window-lookup/main_output.cpp', []),
    ('contract-entry.cpp', base / 'main.cpp', ['-Dmain=unused_main']),
    ('locked-cache-contract.cpp', experiment / 'stock_locked_cache_contract.cpp', [])
):
    source = output / name
    source.write_bytes(original.read_bytes())
    jobs.append((name + '.o', source, original, guest_flags + extra))

def compile_job(job):
    name, source, original, arguments = job
    obj = output / name
    result = subprocess.run([compiler, *arguments, '-c', str(source), '-o', str(obj)],
        capture_output=True, text=True, timeout=180)
    (output / (name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-4000:]
    print('Compiled', name, flush=True)
    return {'object': name, 'source': source.name, 'baseSource': str(original), 'baseSourceSha256': sha(original),
        'sourceSha256': sha(source), 'objectSha256': sha(obj), 'arguments': arguments}

print('Rebuilding', len(jobs), 'CPU/MMU consumers;', len(dma_sites), 'DMA sites', flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    compiled = list(pool.map(compile_job, jobs))
archive = output / 'libnwiiruntime.a'
subprocess.run(['/usr/bin/ar', 'rcs', str(archive), *[str(output / name) for name in runtime_names]],
    check=True, capture_output=True)
assert set(subprocess.check_output(['/usr/bin/ar', '-t', str(archive)], text=True).splitlines()) - {'__.SYMDEF'} == set(runtime_names)
command = shlex.split((build / 'CMakeFiles/OpenSHSMStockBaseline.dir/link.txt').read_text())
for index in range(75):
    name = f'output_{index}.cpp.o'
    command[command.index('CMakeFiles/OpenSHSMStockBaseline.dir/' + name)] = str(output / name)
command[command.index('CMakeFiles/OpenSHSMStockBaseline.dir/main_output.cpp.o')] = str(output / 'main_output.cpp.o')
command[command.index('CMakeFiles/OpenSHSMStockBaseline.dir/nWiiRuntime/src/core/main.cpp.o')] = str(output / 'main.cpp.o')
command[command.index('nWiiRuntime/libnwiiruntime.a')] = str(archive)
exe = output / 'OpenSHSMStockLockedCache'
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=build, capture_output=True, text=True, timeout=120)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-4000:]
test_command = list(command)
test_command[test_command.index(str(output / 'main.cpp.o'))] = str(output / 'contract-entry.cpp.o')
test_command.insert(1, str(output / 'locked-cache-contract.cpp.o'))
probe = output / 'locked-cache-contract'
test_command[test_command.index('-o') + 1] = str(probe)
result = subprocess.run(test_command, cwd=build, capture_output=True, text=True, timeout=120)
(output / 'contract-link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-4000:]
result = subprocess.run([str(probe)], capture_output=True, text=True, timeout=20)
(output / 'contract.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stdout + result.stderr
assert dol_path.read_bytes() == dol
(output / 'build.json').write_text(json.dumps({'result': 'LOCKED_CACHE_FULL_CONSUMER_REBUILD',
    'compiled': compiled, 'dmaSites': dma_sites, 'baseArchiveSha256': sha(base_archive),
    'archiveSha256': sha(archive), 'executableSha256': sha(exe), 'contractExecutableSha256': sha(probe),
    'cpuBaseHeaderSha256': sha(cpu_base), 'cpuHeaderSha256': sha(headers / cpu_base.name),
    'processorHeaderSha256': sha(output / 'processor_adapter.h'), 'contract': result.stdout.strip(),
    'limits': ['256KiB linear cache backing and synchronous DMA follow Dolphin approximation, not cycle-exact physical Wii.',
        'RAM/cache transfer only; EFB/MMIO DMA, queue flush, wrapped spans and guest exception vectors refused/unimplemented.',
        'All native CPU/MMU consumers recompiled; no prior ABI objects linked.',
        'Component test is not THP pixel/retail boot/menu/audio/controller acceptance.']}, indent=2) + '\n')
print(result.stdout.strip(), flush=True)

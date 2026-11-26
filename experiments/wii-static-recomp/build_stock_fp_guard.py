"""Integrate checked FP availability with existing dispatcher/SDK; no production changes."""
from pathlib import Path
import concurrent.futures
import hashlib
import json
import shutil
import subprocess
from stock_fp_guard_lowering import lower
from stock_fp_unavailable_patch import adapt_interpreter

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
full, base = root / 'window-quantization', root / 'window-fp-lazy-context'
output = root / 'window-fp-guard'
output.mkdir(exist_ok=True)
public = Path('experiments/wii-static-recomp').resolve()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((base / 'build.json').read_text())
parent = json.loads((full / 'build.json').read_text())
reference = json.loads((root / 'fp-guard-component/report.json').read_text())
assert reference['result'] == 'FP_CLASSIFICATION_NONLOCAL_COMPONENT_PASS'
for item in reference['inputs']:
    assert sha(Path(item['path'])) == item['sha256'], item['path']
assert sha(base / 'OpenSHSMStockFPLazyContext') == build['executableSha256']
assert sha(base / 'libnwiiruntime.a') == build['archiveSha256']
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
command = list(build['linkCommand'])
def compile_guest(index):
    name = f'output_{index}.cpp'
    item = next(row for row in parent['compiled'] if row['source'] == name)
    original = root / 'window-thp-dcbz/output_37.cpp' if index == 37 else full / name
    text, sites, fpscr = lower(original.read_text(), dol, reference['tables'])
    original_object = original.with_name(original.name + '.o')
    if not sites:
        return {'source': name, 'retainedPath': str(original_object), 'retainedSha256': sha(original_object), 'sites': []}
    source, obj = output / name, output / (name + '.o')
    arguments = [*item['arguments'], '-I', str(public)]
    record_path = output / (name + '.record.json')
    dependencies = {str(path): sha(path) for path in [public / 'stock_fp_unavailable.h', public / 'fpscr_adapter.h',
        full / 'include/runtime/cpu_context.h', full / 'processor_adapter.h']}
    if record_path.exists() and source.exists() and obj.exists():
        cached = json.loads(record_path.read_text())
        if (source.read_text() == text and cached['sourceSha256'] == sha(source)
            and cached['objectSha256'] == sha(obj) and cached['arguments'] == arguments
            and cached['dependencies'] == dependencies and cached['sites'] == sites and cached['fpscrLowerings'] == fpscr):
            print('Reused verified', name, flush=True)
            return cached
    source.write_text(text)
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
        '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
    (output / (name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-3000:]
    print('Compiled', name, 'guards=', len(sites), flush=True)
    record = {'source': name, 'baseSourcePath': str(original), 'baseSourceSha256': sha(original),
        'sourceSha256': sha(source), 'objectSha256': sha(obj), 'object': str(obj),
        'arguments': arguments, 'sites': sites, 'fpscrLowerings': fpscr, 'dependencies': dependencies}
    record_path.write_text(json.dumps(record, indent=2) + '\n')
    return record

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    compiled = list(pool.map(compile_guest, range(75)))
for item in compiled:
    if item['sites']:
        name = item['source'] + '.o'
        matches = [i for i, path in enumerate(command) if path.endswith('/' + name)]
        assert len(matches) == 1
        command[matches[0]] = item['object']
interpreter = output / 'interpreter.cpp'
text = adapt_interpreter((full / 'interpreter.cpp').read_text(), complete=True)
text = text.replace('#include "stock_fp_unavailable.h"\n', '#include "stock_fp_unavailable.h"\n#include "fpscr_adapter.h"\n')
text = text.replace('case 38: case 70: case 134: case 711: break;',
    'case 711: experiment_mtfsf(ctx, insn); break;\n        case 38: case 70: case 134: break;')
interpreter.write_text(text)
item = next(row for row in parent['compiled'] if row['source'] == 'interpreter.cpp')
obj = output / 'interpreter.cpp.o'
arguments = [*item['arguments'], '-I', str(public)]
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-c', str(interpreter), '-o', str(obj)], capture_output=True, text=True, timeout=60)
(output / 'interpreter-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
archive = output / 'libnwiiruntime.a'
shutil.copy2(base / 'libnwiiruntime.a', archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], check=True, capture_output=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
retained_runtime = {}
for member in parent['runtimeMembers']:
    if member == obj.name:
        continue
    original = subprocess.check_output(['/usr/bin/ar', '-p', str(base / 'libnwiiruntime.a'), member])
    assert original == subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    retained_runtime[member] = hashlib.sha256(original).hexdigest()
command[command.index(str(base / 'libnwiiruntime.a'))] = str(archive)
exe = output / 'OpenSHSMStockFPGuard'
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=60)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
(output / 'build.json').write_text(json.dumps({'result': 'FP_GUARDS_INTEGRATED_BOOT_UNVERIFIED',
    'baseBuildSha256': sha(base / 'build.json'), 'fullBuildSha256': sha(full / 'build.json'),
    'compiled': compiled, 'guardCount': sum(len(row['sites']) for row in compiled),
    'interpreterSourceSha256': sha(interpreter), 'interpreterObjectSha256': sha(obj),
    'interpreterArguments': arguments, 'archiveSha256': sha(archive), 'retainedRuntimeMembers': retained_runtime,
    'linkCommand': command, 'executableSha256': sha(exe),
    'dependencies': {str(path): sha(path) for path in [public / 'stock_fp_unavailable.h', public / 'fpscr_adapter.h',
        public / 'stock_fp_guard_lowering.py', public / 'stock_fp_unavailable_patch.py', Path(__file__).resolve()]},
    'limits': ['Boot and independent original execution unverified; no menu/pixel acceptance.',
        'Invalid paired execution profiles refuse before FPU trap; program exception delivery not implemented.',
        'mffs low FPSCR word transferred; exact unspecified upper payload/hardware behavior not verified.',
        'Existing FPSCR/rounding/NaN/PSQ arithmetic fidelity limitations remain.']}, indent=2) + '\n')
print('Linked', exe.name, 'guards=', sum(len(row['sites']) for row in compiled), flush=True)

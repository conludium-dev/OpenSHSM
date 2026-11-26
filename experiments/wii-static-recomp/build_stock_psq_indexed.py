"""Lower all byte-checked indexed PSQ sites through the same bounded-profile runtime adapter."""
from pathlib import Path
import concurrent.futures
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import argparse
from stock_psq_patch import lower_indexed
from stock_byte_reverse_patch import lower_byte_reverse
from stock_logical_record_patch import lower_logical_record

parser = argparse.ArgumentParser()
parser.add_argument('--byte-reverse', action='store_true')
parser.add_argument('--logical-record', action='store_true')
parser.add_argument('--optimized', action='store_true')
args = parser.parse_args()
assert not args.logical_record or args.byte_reverse
assert not args.optimized or args.logical_record

project = Path('.').resolve()
root = project / 'work/private-game/static-recomp/stock-baseline'
build = root / 'export/build'
output = root / ('window-optimized' if args.optimized else 'window-logical-record' if args.logical_record else 'window-byte-reverse' if args.byte_reverse else 'window-psq')
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
dol_path = project / 'work/private-game/disc/DATA/sys/main.dol'
dol = dol_path.read_bytes()
assert hashlib.sha256(dol).hexdigest() == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
header = project / 'experiments/wii-static-recomp/stock_psq_indexed.h'
shutil.copy2(header, output / header.name)
flags = (build / 'CMakeFiles/OpenSHSMStockBaseline.dir/flags.make').read_text()
compiler = re.search(r'# compile CXX with (.+)', flags)[1]
arguments = []
for name in ('CXX_DEFINES', 'CXX_INCLUDES', 'CXX_FLAGS'):
    arguments += shlex.split(re.search(r'^' + name + r' = (.*)$', flags, re.M)[1])
arguments += ['-I', str(root / 'export'), '-I', str(output)]
if args.optimized:
    arguments += ['-O2', '-fno-strict-aliasing', '-fwrapv', '-ffp-contract=off']
assert not any(value in arguments for value in ('-DNDEBUG', '-ffast-math', '-Ofast'))
recipe = project / 'experiments/wii-static-recomp/stock_psq_contract.cpp'
probe = output / 'psq-contract'
subprocess.run([compiler, *arguments, str(recipe), '-o', str(probe)], check=True, timeout=60)
result = subprocess.run([str(probe)], capture_output=True, text=True, timeout=20)
(output / 'contract.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stdout + result.stderr
changed = []
for index in range(75):
    original = root / 'export' / f'output_{index}.cpp'
    text, sites = lower_indexed(original.read_text(), dol)
    reverse_sites = []
    if args.byte_reverse:
        text, reverse_sites = lower_byte_reverse(text, dol)
    logical_sites = []
    if args.logical_record:
        text, logical_sites = lower_logical_record(text, dol)
    if sites or reverse_sites or logical_sites or args.optimized:
        source = output / original.name
        source.write_text(text)
        changed.append((index, source, sites, sha(original), reverse_sites, logical_sites))
assert any(site['address'] == 0x8034C2D4 for _, _, sites, _, _, _ in changed for site in sites)
print('Byte-checked', sum(len(item[5]) for item in changed), 'logical record sites;', len(changed), 'batches; compiling', flush=True)
def compile_batch(item):
    index, source, sites, base_hash, reverse_sites, logical_sites = item
    obj = output / f'output_{index}.cpp.o'
    previous_variant = root / ('window-byte-reverse' if args.logical_record else 'window-psq')
    previous = previous_variant / source.name
    previous_obj = previous_variant / obj.name
    if args.byte_reverse and not args.optimized and previous.exists() and previous.read_bytes() == source.read_bytes():
        shutil.copy2(previous_obj, obj)
        return {'index': index, 'sites': sites, 'reverseSites': reverse_sites, 'logicalSites': logical_sites, 'baseSha256': base_hash,
            'sourceSha256': sha(source), 'objectSha256': sha(obj), 'reusedPSQObject': True}
    result = subprocess.run([compiler, *arguments, '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
    (output / f'compile_{index}.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-3000:]
    print('Compiled batch', index, flush=True)
    return {'index': index, 'sites': sites, 'reverseSites': reverse_sites, 'logicalSites': logical_sites, 'baseSha256': base_hash,
        'sourceSha256': sha(source), 'objectSha256': sha(obj)}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    modules = list(pool.map(compile_batch, changed))
command = shlex.split((build / 'CMakeFiles/OpenSHSMStockBaseline.dir/link.txt').read_text())
entry_name = 'CMakeFiles/OpenSHSMStockBaseline.dir/nWiiRuntime/src/core/main.cpp.o'
dispatch_name = 'CMakeFiles/OpenSHSMStockBaseline.dir/main_output.cpp.o'
command[command.index(entry_name)] = str(root / 'window-paced/main.cpp.o')
command[command.index(dispatch_name)] = str(root / 'window-lookup/main_output.cpp.o')
retained = {}
changed_indices = {item['index'] for item in modules}
for index in range(75):
    name = f'CMakeFiles/OpenSHSMStockBaseline.dir/output_{index}.cpp.o'
    if index in changed_indices:
        command[command.index(name)] = str(output / f'output_{index}.cpp.o')
    else:
        retained[name] = sha(build / name)
archive = root / 'ipc-cpbp/libnwiiruntime.a'
command[command.index('nWiiRuntime/libnwiiruntime.a')] = str(archive)
exe = output / ('OpenSHSMStockOptimized' if args.optimized else 'OpenSHSMStockLogicalRecord' if args.logical_record else 'OpenSHSMStockByteReverse' if args.byte_reverse else 'OpenSHSMStockPSQIndexed')
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=build, capture_output=True, text=True, timeout=120)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
assert dol_path.read_bytes() == dol
(output / 'build.json').write_text(json.dumps({
    'result': 'LOGICAL_RECORD_BYTE_REVERSE_AND_INDEXED_PSQ_BUILT' if args.logical_record else 'BYTE_REVERSE_RA_ZERO_AND_INDEXED_PSQ_BUILT' if args.byte_reverse else 'INDEXED_PSQ_FLOAT_PROFILE_BUILT', 'modules': modules,
    'byteReverseRAZero': args.byte_reverse,
    'logicalRecord': args.logical_record,
    'optimizedGuestOnly': args.optimized,
    'retainedGuestObjects': retained, 'headerSha256': sha(header),
    'entrySha256': sha(root / 'window-paced/main.cpp.o'),
    'dispatcherSha256': sha(root / 'window-lookup/main_output.cpp.o'),
    'archiveSha256': sha(archive), 'executableSha256': sha(exe),
    'contractOutput': (output / 'contract.log').read_text(),
    'limits': ['Addressing/W/update/register variants covered, only finite float GQR profile admitted.',
        'Integer scaling/saturation and nonrepresentable/nonfinite stores explicitly refused.',
        'Contract uses RAM and trapping host stubs, not original Wii CPU/DSI/entire numeric proof.',
        'Full startup and original-reference evidence required; no removed guest init or synthesized state.']
}, indent=2) + '\n')
print('Built;', sum(not item.get('reusedPSQObject', False) for item in modules), 'compiled /',
    sum(item.get('reusedPSQObject', False) for item in modules), 'PSQ objects reused /', len(retained), 'base batches retained')

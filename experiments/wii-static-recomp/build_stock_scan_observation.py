"""Build one read-only observed guest object on the verified scan-route runtime."""
from pathlib import Path
import hashlib
import json
import subprocess
import argparse
import shutil
from stock_scan_observation import adapt
from stock_scan_consumption import adapt_caller, adapt_interpreter, IMPLEMENTATION

parser = argparse.ArgumentParser()
parser.add_argument('--consumption', action='store_true')
args = parser.parse_args()
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base = root / 'window-scan-routes'
output = root / ('window-scan-consume' if args.consumption else 'window-scan-observe')
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((base / 'build.json').read_text())
assert sha(base / 'OpenSHSMStockScanRoutes') == build['executableSha256']
dol = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
item = next(row for row in build['compiled'] if row['source'] == 'output_31.cpp')
assert sha(base / 'output_31.cpp') == item['sourceSha256']
source, obj = output / 'output_31.cpp', output / 'output_31.cpp.o'
source.write_text(adapt((base / 'output_31.cpp').read_text(), dol.read_bytes()) + (IMPLEMENTATION if args.consumption else ''))
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *item['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=120)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
command = list(build['linkCommand'])
command[command.index(str(base / 'output_31.cpp.o'))] = str(obj)
caller = None
runtime = None
if args.consumption:
    original_caller = next(Path(arg) for arg in command if Path(arg).name == 'output_19.cpp.o').with_suffix('')
    caller_source, caller_obj = output / 'output_19.cpp', output / 'output_19.cpp.o'
    caller_source.write_text(adapt_caller(original_caller.read_text(), dol.read_bytes()))
    full = json.loads((root / 'window-quantization/build.json').read_text())
    arguments = next(row for row in full['compiled'] if row['source'] == 'output_19.cpp')['arguments']
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
        '-c', str(caller_source), '-o', str(caller_obj)], capture_output=True, text=True, timeout=120)
    (output / 'caller-compile.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    command[command.index(str(original_caller) + '.o')] = str(caller_obj)
    caller = {'originalPath': str(original_caller), 'originalSha256': sha(original_caller),
        'sourceSha256': sha(caller_source), 'objectSha256': sha(caller_obj), 'arguments': arguments}
    guard = root / 'window-fp-guard'
    guard_build = json.loads((guard / 'build.json').read_text())
    assert sha(guard / 'interpreter.cpp') == guard_build['interpreterSourceSha256']
    interpreter, interpreter_obj = output / 'interpreter.cpp', output / 'interpreter.cpp.o'
    interpreter.write_text(adapt_interpreter((guard / 'interpreter.cpp').read_text()))
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *guard_build['interpreterArguments'],
        '-c', str(interpreter), '-o', str(interpreter_obj)], capture_output=True, text=True, timeout=60)
    (output / 'interpreter-compile.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    original_archive = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
    assert sha(original_archive) == guard_build['archiveSha256']
    archive = output / 'libnwiiruntime.a'
    shutil.copy2(original_archive, archive)
    subprocess.run(['/usr/bin/ar', 'r', str(archive), str(interpreter_obj)], check=True, capture_output=True)
    subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
    members = subprocess.check_output(['/usr/bin/ar', 't', str(original_archive)], text=True).splitlines()
    retained = {}
    for member in members:
        if member == 'interpreter.cpp.o' or member.startswith('__.SYMDEF'):
            continue
        data = subprocess.check_output(['/usr/bin/ar', '-p', str(original_archive), member])
        assert data == subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
        retained[member] = hashlib.sha256(data).hexdigest()
    command[command.index(str(original_archive))] = str(archive)
    runtime = {'originalPath': str(original_archive), 'originalSha256': sha(original_archive),
        'sourceSha256': sha(interpreter), 'objectSha256': sha(interpreter_obj), 'archiveSha256': sha(archive),
        'retainedMembers': retained, 'arguments': guard_build['interpreterArguments']}
exe = output / ('OpenSHSMStockScanConsumer' if args.consumption else 'OpenSHSMStockScanObserver')
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=60)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
(output / 'build.json').write_text(json.dumps({'result': 'BOUNDED_READ_ONLY_SCAN_OBSERVER',
    'sourceSha256': sha(source), 'objectSha256': sha(obj), 'baseBuildSha256': sha(base / 'build.json'),
    'headerSha256': sha(Path('experiments/wii-static-recomp/stock_scan_observation.h')),
    'consumption': args.consumption, 'caller': caller, 'runtime': runtime,
    'consumptionHeaderSha256': sha(Path('experiments/wii-static-recomp/stock_scan_consumption.h')) if args.consumption else None,
    'arguments': item['arguments'], 'linkCommand': command, 'executableSha256': sha(exe),
    'dispatcherPath': str(base / 'main_output.cpp'),
    'retainedInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file()
        and Path(arg).suffix in ('.o', '.a') and arg not in {str(obj), str(output / 'output_19.cpp.o'), str(output / 'libnwiiruntime.a')}},
    'limits': ['Host-only observation: 32 total/4 distinct inputs per format, 256byte strings/six 8byte output snapshots.',
        'Pending pairing by CPUContext+entry SP, not complete thread/IRQ snapshot; direct RAM reads only, no guest writes.',
        'Caller consumption observation installed but unverified by build alone; no original oracle acceptance.' if args.consumption
            else 'Snapshots at return continuation before epilogue; no caller consumption or original oracle acceptance.']}, indent=2) + '\n')
print('Built bounded scan consumer observer; two guest objects and one interpreter member replaced' if args.consumption
    else 'Built bounded read-only original scan observer; one guest object replaced')

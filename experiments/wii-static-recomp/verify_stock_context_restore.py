"""Exercise the actual linked IOS restore with finite fixtures; not original Wii acceptance."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base = root / 'window-sdk-enable-resume'
output = root / 'context-restore-fixtures'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = base / 'build.json'
build = json.loads(build_path.read_text())
assert sha(base / 'OpenSHSMStockSDKEnableResume') == build['executableSha256']
command = list(build['records']['fixed']['linkCommand'])
archive = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
ios = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), 'ios.cpp.o'])
ios_source = root / 'window-fp-lazy-context/ios.cpp'
assert ios == (ios_source.with_suffix('.cpp.o')).read_bytes()
source = Path('experiments/wii-static-recomp/stock_context_restore_probe.cpp').resolve()
full = json.loads((root / 'window-quantization/build.json').read_text())
arguments = next(row['arguments'] for row in full['compiled'] if row['source'] == 'main_output.cpp')
obj = output / 'probe.cpp.o'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=60)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
command[command.index(str(base / 'probe.cpp.o'))] = str(obj)
exe = output / 'context-restore-probe'
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=60)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=20)
(output / 'probe.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stdout + result.stderr
assert result.stdout.count('RESTORE ') == 8 and 'LINKED_CONTEXT_RESTORE_FIXTURES_PASS 8' in result.stdout
report = {'result': 'LINKED_CONTEXT_RESTORE_FIXTURES_PASS', 'cases': 8,
    'baseBuildSha256': sha(build_path), 'sourceSha256': sha(source), 'objectSha256': sha(obj),
    'executableSha256': sha(exe), 'logSha256': sha(output / 'probe.log'),
    'archiveSha256': sha(archive), 'linkedIosObjectSha256': hashlib.sha256(ios).hexdigest(),
    'linkedIosSourceSha256': sha(ios_source), 'linkCommand': command,
    'recipeSha256': sha(Path(__file__)), 'output': result.stdout,
    'limits': ['Actual linked host IOS restore, supplied guest context/thread fixtures; no original SDK scheduling execution.',
        'Four selection routes, valid/zero PC, lazy FP preservation. Accepting zero PC is reproduced, not fixed.',
        'Does not prove which live context was selected, who wrote zero or that preferring current thread is incorrect.',
        'No game launch, forced readiness/IRQ/counter/guard or production runtime change.']}
(output / 'component.json').write_text(json.dumps(report, indent=2) + '\n')
print(result.stdout)

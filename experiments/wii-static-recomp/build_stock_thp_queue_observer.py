"""Extend the existing THP trace observation; retain all guest code and other runtime objects."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base, output = root / 'interpreter-addze-corrected', root / 'window-movie-queues'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((base / 'build.json').read_text())
assert sha(base / 'OpenSHSMStockInterpreterAddze') == build['executableSha256']
command = list(build['linkCommand'])
full = root / 'window-quantization'
item = next(row for row in json.loads((full / 'build.json').read_text())['compiled'] if row['source'] == 'os_hle_stubs.cpp')
original = full / 'os_hle_stubs.cpp'
assert sha(original) == item['sourceSha256']
old_archive = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
assert sha(old_archive) == build['runtime']['archiveSha256']
assert hashlib.sha256(subprocess.check_output(['/usr/bin/ar', '-p', str(old_archive), 'os_hle_stubs.cpp.o'])).hexdigest() == item['objectSha256']
text = original.read_text()
marker = '  if (!g_trace_only.empty() && !g_trace_only.count(func_addr)) return;'
assert text.count(marker) == 1
text = '#include "stock_thp_queue_observation.h"\n' + text.replace(marker,
    marker + '\n  stock_thp_queue_observation::observe(ctx, func_addr);')
source, obj = output / 'os_hle_stubs.cpp', output / 'os_hle_stubs.cpp.o'
source.write_text(text)
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *item['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=60)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
archive = output / 'libnwiiruntime.a'
shutil.copy2(old_archive, archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], check=True, capture_output=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
retained = {}
for member in subprocess.check_output(['/usr/bin/ar', 't', str(old_archive)], text=True).splitlines():
    if member == 'os_hle_stubs.cpp.o' or member.startswith('__.SYMDEF'):
        continue
    data = subprocess.check_output(['/usr/bin/ar', '-p', str(old_archive), member])
    assert data == subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    retained[member] = hashlib.sha256(data).hexdigest()
command[command.index(str(old_archive))] = str(archive)
exe = output / 'OpenSHSMStockMovieQueues'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=60)
(output / 'build.json').write_text(json.dumps({'baseBuildSha256': sha(base / 'build.json'),
    'originalSourceSha256': sha(original), 'sourceSha256': sha(source), 'objectSha256': sha(obj),
    'headerSha256': sha(Path('experiments/wii-static-recomp/stock_thp_queue_observation.h')),
    'copyHelperSha256': sha(Path('experiments/wii-static-recomp/stock_loading_observation.h')),
    'archiveSha256': sha(archive), 'retainedMembers': retained, 'arguments': item['arguments'],
    'linkCommand': command, 'executableSha256': sha(exe),
    'retainedInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file()
        and Path(arg).suffix in ('.o', '.a') and arg != str(archive)},
    'limits': ['Before-call metadata only: receiver argument is not a completed receive result.',
        'Movie LR80090000..8009FFFF only;128site keys/first16 then every60/20000event cap.',
        'No guest writes, no queue success/readiness forcing, no full activation/IRQ correlation.']}, indent=2) + '\n')
print('Built bounded movie queue observation; one runtime member changed')

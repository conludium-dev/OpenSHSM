"""Extend the existing THP observation with one bounded native decoder entry snapshot."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'headless-thp-snapshot'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base_path = root / 'headless-constant-fp/build.json'
base = json.loads(base_path.read_text())
for path, expected in {**base['dependencies'], **base['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
command = list(base['linkCommand'])
old = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
assert sha(old) == base['archiveSha256']
prior = json.loads((root / 'window-movie-queues/build.json').read_text())
original = root / 'window-movie-queues/os_hle_stubs.cpp'
assert sha(original) == prior['sourceSha256']
assert hashlib.sha256(subprocess.check_output(['/usr/bin/ar', '-p', str(old), 'os_hle_stubs.cpp.o'])).hexdigest() == prior['objectSha256']
text = original.read_text()
marker = 'static void observe_thp(uint32_t function, CPUContext& ctx) {'
assert text.count(marker) == 1
text = '#include "stock_thp_snapshot.h"\n' + text.replace(marker, marker +
    '\n    if (function == 0x80209D80) { stock_thp_snapshot::observe(ctx); }')
source, obj = output / 'os_hle_stubs.cpp', output / 'os_hle_stubs.cpp.o'
source.write_text(text)
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *prior['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
archive = output / 'libnwiiruntime.a'
shutil.copy2(old, archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], capture_output=True, check=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], capture_output=True, check=True)
retained = {}
for member in subprocess.check_output(['/usr/bin/ar', '-t', str(old)], text=True).splitlines():
    if member.startswith('__') or member == 'os_hle_stubs.cpp.o':
        continue
    data = subprocess.check_output(['/usr/bin/ar', '-p', str(old), member])
    assert data == subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    retained[member] = hashlib.sha256(data).hexdigest()
command[command.index(str(old))] = str(archive)
exe = output / 'OpenSHSMStockTHPSnapshot'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
(output / 'build.json').write_text(json.dumps({'result': 'THP_SNAPSHOT_BUILT_CAPTURE_UNVERIFIED',
    'baseBuildSha256': sha(base_path), 'originalSourceSha256': sha(original), 'sourceSha256': sha(source),
    'objectSha256': sha(obj), 'archiveSha256': sha(archive), 'executableSha256': sha(exe), 'linkCommand': command,
    'retainedRuntimeMembers': retained, 'dependencies': {str(path): sha(path) for path in
        [Path(__file__).resolve(), public / 'stock_thp_snapshot.h', root / 'window-quantization/processor_adapter.h']},
    'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).suffix == '.o'},
    'limits': ['One native little-endian SHSMFP01 snapshot: CPU registers +3backedRAM banks at original decode entry.',
        'No guest writes; host runtime queues/devices/instructionImages not serialized; not original Wii save-state.',
        'Snapshot disk I/O affects live timing; one runtime object replaced/all75guest objects retained.']}, indent=2) + '\n')
print('THP_SNAPSHOT_BUILT_CAPTURE_UNVERIFIED')

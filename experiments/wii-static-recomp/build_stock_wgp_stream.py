"""Replace GX diagnostic hooks only on the verified FP-guard runtime."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
from stock_wgp_stream_patch import adapt

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base, full, output = root / 'window-fp-guard', root / 'window-quantization', root / 'window-wgp-stream'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((base / 'build.json').read_text())
parent = json.loads((full / 'build.json').read_text())
assert sha(base / 'OpenSHSMStockFPGuard') == build['executableSha256']
assert sha(base / 'libnwiiruntime.a') == build['archiveSha256']
item = next(row for row in parent['compiled'] if row['source'] == 'gx.cpp')
assert sha(full / 'gx.cpp') == item['sourceSha256']
source, obj = output / 'gx.cpp', output / 'gx.cpp.o'
source.write_text(adapt((full / 'gx.cpp').read_text()))
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *item['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=60)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
archive = output / 'libnwiiruntime.a'
shutil.copy2(base / 'libnwiiruntime.a', archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], check=True, capture_output=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
retained = {}
for member in parent['runtimeMembers']:
    if member == 'gx.cpp.o':
        continue
    before = subprocess.check_output(['/usr/bin/ar', '-p', str(base / 'libnwiiruntime.a'), member])
    assert before == subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    retained[member] = hashlib.sha256(before).hexdigest()
command = list(build['linkCommand'])
command[command.index(str(base / 'libnwiiruntime.a'))] = str(archive)
exe = output / 'OpenSHSMStockWGPStream'
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=60)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
(output / 'build.json').write_text(json.dumps({'result': 'READ_ONLY_LINKED_WGP_STREAM_CAPTURE',
    'sourceSha256': sha(source), 'objectSha256': sha(obj), 'archiveSha256': sha(archive),
    'baseBuildSha256': sha(base / 'build.json'), 'fullBuildSha256': sha(full / 'build.json'),
    'arguments': item['arguments'], 'linkCommand': command, 'executableSha256': sha(exe),
    'retainedRuntimeMembers': retained,
    'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file()
        and Path(arg).suffix in ('.o', '.a') and arg != str(archive)},
    'limits': ['Capture hooks observe accepted bytes and committed actual gather bursts; no guest FIFO/padding/idle changes.',
        'Binary/segments cap16MiB, burst cap524288; reaching cap means incomplete capture, not accepted full stream.',
        'Logging changes host throughput; sampled ctx.pc can be stale, not an exact producer instruction address.']}, indent=2) + '\n')
print('Built read-only linked WGP stream observer; 77guest objects/44runtime members retained')

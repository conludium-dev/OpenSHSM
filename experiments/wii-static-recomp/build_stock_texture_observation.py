"""Observe actual newly decoded textures, retaining rendering and guest behavior."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
base_path = root / 'window-ipc-reply/build.json'
base = json.loads(base_path.read_text())
for path, expected in base['dependencies'].items():
    assert sha(Path(path)) == expected
for path, expected in base['retainedLinkInputs'].items():
    assert sha(Path(path)) == expected
output = root / 'window-texture-observe'
output.mkdir(exist_ok=True)
original = root / 'window-quantization/texture_cache_gl.cpp'
record = next(row for row in json.loads((root / 'window-quantization/build.json').read_text())['compiled']
    if row['source'] == 'texture_cache_gl.cpp')
assert sha(original) == record['sourceSha256']
marker = '    Image img = decode_texture(ctx, stage);\n'
text = original.read_text()
assert text.count(marker) == 1
text = '#include "stock_texture_observation.h"\n' + text.replace(marker,
    marker + '    openshsm::experiment::observe_texture(ctx, stage, hash, img);\n')
source, obj = output / 'texture_cache_gl.cpp', output / 'texture_cache_gl.cpp.o'
source.write_text(text)
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=60)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
command = list(base['linkCommand'])
old = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
assert sha(old) == base['archiveSha256']
assert subprocess.check_output(['/usr/bin/ar', '-p', str(old), obj.name]) == (root / 'window-quantization' / obj.name).read_bytes()
archive = output / 'libnwiiruntime.a'
shutil.copy2(old, archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], capture_output=True, check=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], capture_output=True, check=True)
retained = {}
for member in subprocess.check_output(['/usr/bin/ar', '-t', str(old)], text=True).splitlines():
    if member == obj.name or member.startswith('__'):
        continue
    before = subprocess.check_output(['/usr/bin/ar', '-p', str(old), member])
    assert before == subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    retained[member] = hashlib.sha256(before).hexdigest()
command[command.index(str(old))] = str(archive)
exe = output / 'OpenSHSMStockTextureObserve'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=60)
probe_source, probe_obj = public / 'stock_texture_observation_probe.cpp', output / 'probe.cpp.o'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
    '-c', str(probe_source), '-o', str(probe_obj)], capture_output=True, text=True, timeout=60)
(output / 'probe-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
probe_command = list(command)
probe_command[probe_command.index(str(root / 'window-quantization/main.cpp.o'))] = str(root / 'window-quantization/contract-entry.cpp.o')
probe_command.insert(1, str(probe_obj))
probe_exe = output / 'observer-probe'
probe_command[probe_command.index('-o') + 1] = str(probe_exe)
subprocess.run(probe_command, cwd=root / 'export/build', capture_output=True, check=True, timeout=60)
import tempfile
probe_directory = Path(tempfile.mkdtemp(prefix='observer-probe-', dir=output))
result = subprocess.run([str(probe_exe), str(probe_directory)], capture_output=True, text=True, timeout=20)
(output / 'probe.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and 'TEXTURE_OBSERVER_COMPONENT_PASS' in result.stdout, result.stderr
(output / 'build.json').write_text(json.dumps({'result': 'TEXTURE_OBSERVER_BUILT_LIVE_UNVERIFIED',
    'baseBuildSha256': sha(base_path), 'originalSourceSha256': sha(original), 'sourceSha256': sha(source),
    'objectSha256': sha(obj), 'archiveSha256': sha(archive), 'executableSha256': sha(exe), 'linkCommand': command,
    'dependencies': {str(p): sha(p) for p in [Path(__file__).resolve(), public / 'stock_texture_observation.h', probe_source]},
    'probeExecutableSha256': sha(probe_exe), 'probeLogSha256': sha(output / 'probe.log'),
    'retainedRuntimeMembers': retained, 'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command
        if Path(arg).is_file() and Path(arg).suffix in ('.o', '.a') and arg != str(archive)},
    'limits': ['Read-only guest bytes/decoded RGBA/BP snapshots on cache misses, no GPU or guest writes.',
        'Maximum128 snapshots,2per address/dimensions/format,96MiB total; not all texture updates or EFB hits.',
        'Observation overhead is not original Wii timing; no render/profile/playable success from build.']}, indent=2) + '\n')
print('TEXTURE_OBSERVER_BUILT_LIVE_UNVERIFIED retained runtime', len(retained))

"""Build a private scoped shader variant and real-driver probes; retain all guest code."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
from stock_tev_scope_patch import generator, renderer

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
base_path = root / 'window-fs-rename/build.json'
base = json.loads(base_path.read_text())
for path, expected in base['dependencies'].items():
    assert sha(Path(path)) == expected
for path, expected in base['retainedLinkInputs'].items():
    assert sha(Path(path)) == expected
output = root / 'window-tev-scope'
output.mkdir(exist_ok=True)
records = json.loads((root / 'window-quantization/build.json').read_text())['compiled']
command = list(base['linkCommand'])
old = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
assert sha(old) == base['archiveSha256']
archive = output / 'libnwiiruntime.a'
shutil.copy2(old, archive)
compiled = []
def compile_file(src, obj, arguments):
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
        '-c', str(src), '-o', str(obj)], capture_output=True, text=True, timeout=60)
    (output / (obj.name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
for name, adapt in [('tev_shader_gen.cpp', generator), ('renderer_gl.cpp', renderer)]:
    original = root / 'window-quantization' / name
    record = next(row for row in records if row['source'] == name)
    assert sha(original) == record['sourceSha256']
    source, obj = output / name, output / (name + '.o')
    source.write_text(adapt(original.read_text()))
    compile_file(source, obj, record['arguments'])
    assert subprocess.check_output(['/usr/bin/ar', '-p', str(old), obj.name]) == (root / 'window-quantization' / obj.name).read_bytes()
    subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], check=True, capture_output=True)
    compiled.append({'source': name, 'originalSourceSha256': sha(original), 'sourceSha256': sha(source), 'objectSha256': sha(obj)})
subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
retained = {}
for member in subprocess.check_output(['/usr/bin/ar', '-t', str(old)], text=True).splitlines():
    if member in ('tev_shader_gen.cpp.o', 'renderer_gl.cpp.o') or member.startswith('__'):
        continue
    data = subprocess.check_output(['/usr/bin/ar', '-p', str(old), member])
    assert data == subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    retained[member] = hashlib.sha256(data).hexdigest()
command[command.index(str(old))] = str(archive)
exe = output / 'OpenSHSMStockTEVScope'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=60)
probe_source, probe_obj = public / 'stock_tev_compile_probe.cpp', output / 'probe.cpp.o'
compile_file(probe_source, probe_obj, record['arguments'])
probe_command = list(command)
probe_command[probe_command.index(str(root / 'window-quantization/main.cpp.o'))] = str(root / 'window-quantization/contract-entry.cpp.o')
probe_command.insert(1, str(probe_obj))
probes = {}
for name, runtime in [('baseline', old), ('corrected', archive)]:
    cmd = list(probe_command)
    cmd[cmd.index(str(archive))] = str(runtime)
    probe = output / (name + '-probe')
    cmd[cmd.index('-o') + 1] = str(probe)
    subprocess.run(cmd, cwd=root / 'export/build', check=True, capture_output=True, timeout=60)
    (output / name).mkdir(exist_ok=True)
    probes[name] = {'command': [str(probe), name, str(output / name)], 'executableSha256': sha(probe)}
(output / 'build.json').write_text(json.dumps({'result': 'TEV_SCOPE_BUILT_DRIVER_LIVE_UNVERIFIED',
    'baseBuildSha256': sha(base_path), 'compiled': compiled, 'archiveSha256': sha(archive), 'executableSha256': sha(exe),
    'linkCommand': command, 'probes': probes, 'retainedRuntimeMembers': retained,
    'dependencies': {str(p): sha(p) for p in [Path(__file__).resolve(), public / 'stock_tev_scope_patch.py', probe_source]},
    'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file()
        and Path(arg).suffix in ('.o', '.a') and arg != str(archive)},
    'limits': ['Scope temporary variables only; original TEV equations/register transfer retained.',
        'Existing compiler now checks status, refuses invalid shader and records at most64compile times.',
        'No full Wii GPU fidelity, video performance or visual acceptance from build.']}, indent=2) + '\n')
print('TEV_SCOPE_BUILT_DRIVER_LIVE_UNVERIFIED')

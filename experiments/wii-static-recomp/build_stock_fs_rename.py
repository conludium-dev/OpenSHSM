"""Implement rename in the existing session NAND, leaving prior builds unchanged."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
base_path = root / 'window-buffer-flush-observe/build.json'
base = json.loads(base_path.read_text())
for path, expected in base['dependencies'].items():
    assert sha(Path(path)) == expected
for path, expected in base['retainedLinkInputs'].items():
    assert sha(Path(path)) == expected
output = root / 'window-fs-rename'
output.mkdir(exist_ok=True)
original = root / 'window-nand-hierarchy/fs_device.cpp'
nand = json.loads((root / 'window-nand-hierarchy/build.json').read_text())
assert sha(original) == next(row['sourceSha256'] for row in nand['compiled'] if row['source'] == 'fs_device.cpp')
commands = (public / 'stock_fs_commands.inc').read_text()
marker = '    int32_t ioctl(CPUContext& ctx, const IpcRequest& req) override {\n'
assert commands.count(marker) == 1
commands = commands.replace(marker, '    #include "stock_fs_rename.inc"\n\n' + marker)
marker = '        const uint32_t out = fs_virtual(req.out_buf), in = fs_virtual(req.in_buf);\n'
assert commands.count(marker) == 1
commands = commands.replace(marker, marker + '        if (req.ioctl_cmd == 8) {\n            return rename_node(ctx, req);\n        }\n')
(output / 'stock_fs_rename_commands.inc').write_text(commands)
source, obj = output / 'fs_device.cpp', output / 'fs_device.cpp.o'
text = original.read_text()
assert text.count('#include "stock_fs_commands.inc"') == 1
source.write_text(text.replace('#include "stock_fs_commands.inc"', '#include "stock_fs_rename_commands.inc"'))
arguments = json.loads((root / 'input-snapshot-research/build.json').read_text())['arguments']
def compile_file(src, target):
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
        '-c', str(src), '-o', str(target)], capture_output=True, text=True, timeout=60)
    (output / (target.name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
compile_file(source, obj)
command = list(base['linkCommand'])
old = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
assert subprocess.check_output(['/usr/bin/ar', '-p', str(old), obj.name]) == (root / 'window-nand-hierarchy' / obj.name).read_bytes()
archive = output / 'libnwiiruntime.a'
shutil.copy2(old, archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], capture_output=True, check=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], capture_output=True, check=True)
retained = {}
for member in subprocess.check_output(['/usr/bin/ar', '-t', str(old)], text=True).splitlines():
    if member == obj.name or member.startswith('__'):
        continue
    data = subprocess.check_output(['/usr/bin/ar', '-p', str(old), member])
    assert data == subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    retained[member] = hashlib.sha256(data).hexdigest()
command[command.index(str(old))] = str(archive)
exe = output / 'OpenSHSMStockFSRename'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=60)
probe_source, probe_obj = public / 'stock_fs_rename_probe.cpp', output / 'probe.cpp.o'
compile_file(probe_source, probe_obj)
probe_command = list(command)
probe_command[probe_command.index(str(root / 'window-quantization/main.cpp.o'))] = str(root / 'window-quantization/contract-entry.cpp.o')
probe_command.insert(1, str(probe_obj))
records = {}
for name, runtime, flags, expected in [('baseline', old, ['baseline'], 'BASELINE_RENAME_UNSUPPORTED_REPRODUCED'),
        ('corrected', archive, [], 'FS_RENAME_COMPONENT_PASS')]:
    cmd = list(probe_command)
    cmd[cmd.index(str(archive))] = str(runtime)
    probe = output / (name + '-probe')
    cmd[cmd.index('-o') + 1] = str(probe)
    subprocess.run(cmd, cwd=root / 'export/build', capture_output=True, check=True, timeout=60)
    result = subprocess.run([str(probe), *flags], capture_output=True, text=True, timeout=20)
    log = output / (name + '.log')
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and expected in result.stdout, (name, result.returncode, result.stdout, result.stderr)
    records[name] = {'result': expected, 'executableSha256': sha(probe), 'logSha256': sha(log)}
(output / 'build.json').write_text(json.dumps({'result': 'FS_RENAME_COMPONENT_PASS_LIVE_UNVERIFIED',
    'baseBuildSha256': sha(base_path), 'originalSourceSha256': sha(original), 'sourceSha256': sha(source),
    'generatedCommandsSha256': sha(output / 'stock_fs_rename_commands.inc'), 'objectSha256': sha(obj),
    'archiveSha256': sha(archive), 'executableSha256': sha(exe), 'linkCommand': command, 'records': records,
    'dependencies': {str(p): sha(p) for p in [Path(__file__).resolve(), public / 'stock_fs_rename.inc',
        public / 'stock_fs_commands.inc', public / 'stock_nand_hierarchy.inc', public / 'stock_nand_paths.h', probe_source]},
    'retainedRuntimeMembers': retained, 'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command
        if Path(arg).is_file() and Path(arg).suffix in ('.o', '.a') and arg != str(archive)},
    'sources': ['https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/IOS/FS/FileSystemProxy.h',
        'https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/IOS/FS/FileSystemProxy.cpp'],
    'limits': ['Existing session-only registry; no persistent NAND, complete UID/permission/timing/hardware verification.',
        'Staged subtree paths/closed replacement/tombstone preserve existing handle indices; no second filesystem.',
        'Open-node rename refusal and directory replacement policy are explicit provisional PC adaptations.',
        'Component successful synthetic save commit does not prove full live profile/render/story acceptance.']}, indent=2) + '\n')
print('FS_RENAME_COMPONENT_PASS_LIVE_UNVERIFIED retained runtime', len(retained))

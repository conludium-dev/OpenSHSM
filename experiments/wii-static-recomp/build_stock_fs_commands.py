"""Privately replace one FS archive member; test the exact old false-success sequence first."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
from stock_fs_commands_patch import adapt, adapt_kernel

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-fs-commands'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base_path = root / 'window-input-sdk/build.json'
base = json.loads(base_path.read_text())
for path, expected in base['retainedLinkInputs'].items():
    assert sha(Path(path)) == expected, path
for path, expected in base['dependencies'].items():
    assert sha(Path(path)) == expected, path
assert sha(root / 'window-input-sdk/OpenSHSMStockInputSDK') == base['executableSha256']
arguments = json.loads((root / 'input-snapshot-research/build.json').read_text())['arguments']
original = root / 'export/nWiiRuntime/src/hle/devices/fs_device.cpp'
source, obj = output / 'fs_device.cpp', output / 'fs_device.cpp.o'
source.write_text(adapt(original.read_text()))
def compile_file(source, obj):
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
        '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=60)
    (output / (obj.name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
compile_file(source, obj)
kernel_original = root / 'export/nWiiRuntime/src/hle/ios_kernel.cpp'
kernel_source, kernel_obj = output / 'ios_kernel.cpp', output / 'ios_kernel.cpp.o'
kernel_source.write_text(adapt_kernel(kernel_original.read_text()))
compile_file(kernel_source, kernel_obj)
command = list(base['linkCommand'])
archive_old = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
archive = output / 'libnwiiruntime.a'
shutil.copy2(archive_old, archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], capture_output=True, check=True)
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(kernel_obj)], capture_output=True, check=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], capture_output=True, check=True)
retained = {}
for member in subprocess.check_output(['/usr/bin/ar', '-t', str(archive_old)], text=True).splitlines():
    if member in (obj.name, kernel_obj.name) or member.startswith('__'):
        continue
    before = subprocess.check_output(['/usr/bin/ar', '-p', str(archive_old), member])
    assert before == subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    retained[member] = hashlib.sha256(before).hexdigest()
command[command.index(str(archive_old))] = str(archive)
exe = output / 'OpenSHSMStockFSCommands'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=60)
probe_source = public / 'stock_fs_commands_probe.cpp'
probe_obj = output / 'probe.cpp.o'
compile_file(probe_source, probe_obj)
probe_command = list(command)
probe_command[probe_command.index(str(root / 'window-quantization/main.cpp.o'))] = str(root / 'window-quantization/contract-entry.cpp.o')
probe_command.insert(1, str(probe_obj))
results = {}
for name, runtime, flags, expected in [
    ('baseline', archive_old, ['baseline'], 'BASELINE_FS_FALSE_CREATE_SUCCESS_REPRODUCED'),
    ('corrected', archive, [], 'FS_CREATE_METADATA_USAGE_COMPONENT_PASS')]:
    cmd = list(probe_command)
    cmd[cmd.index(str(archive))] = str(runtime)
    probe = output / (name + '-probe')
    cmd[cmd.index('-o') + 1] = str(probe)
    subprocess.run(cmd, cwd=root / 'export/build', capture_output=True, check=True, timeout=60)
    result = subprocess.run([str(probe), *flags], capture_output=True, text=True, timeout=20)
    log = output / (name + '.log')
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and expected in result.stdout, (name, result.returncode, result.stdout, result.stderr)
    results[name] = {'result': expected, 'executableSha256': sha(probe), 'logSha256': sha(log)}
(output / 'build.json').write_text(json.dumps({'result': 'FS_COMMANDS_COMPONENT_PASS_BOOT_UNVERIFIED',
    'baseBuildSha256': sha(base_path), 'originalSourceSha256': sha(original), 'sourceSha256': sha(source),
    'objectSha256': sha(obj), 'archiveSha256': sha(archive), 'executableSha256': sha(exe),
    'kernelOriginalSha256': sha(kernel_original), 'kernelSourceSha256': sha(kernel_source), 'kernelObjectSha256': sha(kernel_obj),
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), public / 'stock_fs_commands_patch.py',
        public / 'stock_fs_commands.inc', probe_source]}, 'probeObjectSha256': sha(probe_obj), 'records': results,
    'retainedRuntimeMembers': retained, 'linkCommand': command,
    'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file()
        and Path(arg).suffix in ('.o', '.a') and arg != str(archive)},
    'sources': ['https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/IOS/FS/FileSystemProxy.h',
        'https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/IOS/FS/FileSystemProxy.cpp'],
    'limits': ['PC adaptation of existing session-only in-memory registry; no persistent saves or full permission/NAND/timing fidelity.',
        'Create-directory/file, get-attributes/file-stats and get-usage implemented; other commands refused, not fake success.',
        'Live profile progression and rendered-image fidelity remain unverified; synthetic system files retained.']}, indent=2) + '\n')
print('FS_COMMANDS_COMPONENT_PASS_BOOT_UNVERIFIED retained runtime', len(retained))

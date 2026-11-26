"""Add title path and parent directories in private existing ES/FS backends."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
from stock_nand_hierarchy_patch import adapt_es, adapt_fs

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
base_path = root / 'window-fs-commands/build.json'
base = json.loads(base_path.read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
for path, expected in base['dependencies'].items():
    assert sha(Path(path)) == expected, path
for path, expected in base['retainedLinkInputs'].items():
    assert sha(Path(path)) == expected, path
original_fs = root / 'window-fs-commands/fs_device.cpp'
assert sha(original_fs) == base['sourceSha256']
output = root / 'window-nand-hierarchy'
output.mkdir(exist_ok=True)
arguments = json.loads((root / 'input-snapshot-research/build.json').read_text())['arguments']
def compile_file(source, obj):
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
        '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=60)
    (output / (obj.name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
compiled = []
for name, original, adapt in [('fs_device.cpp', original_fs, adapt_fs),
        ('es_device.cpp', root / 'export/nWiiRuntime/src/hle/devices/es_device.cpp', adapt_es)]:
    source, obj = output / name, output / (name + '.o')
    source.write_text(adapt(original.read_text()))
    compile_file(source, obj)
    compiled.append({'source': name, 'originalSourceSha256': sha(original), 'sourceSha256': sha(source), 'objectSha256': sha(obj)})
command = list(base['linkCommand'])
archive_old = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
assert sha(archive_old) == base['archiveSha256']
archive = output / 'libnwiiruntime.a'
shutil.copy2(archive_old, archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), *(str(output / (item['source'] + '.o')) for item in compiled)],
    capture_output=True, check=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], capture_output=True, check=True)
retained = {}
for member in subprocess.check_output(['/usr/bin/ar', '-t', str(archive_old)], text=True).splitlines():
    if member in ('fs_device.cpp.o', 'es_device.cpp.o') or member.startswith('__'):
        continue
    before = subprocess.check_output(['/usr/bin/ar', '-p', str(archive_old), member])
    assert before == subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    retained[member] = hashlib.sha256(before).hexdigest()
command[command.index(str(archive_old))] = str(archive)
exe = output / 'OpenSHSMStockNandHierarchy'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=60)
probe_source, probe_obj = public / 'stock_nand_hierarchy_probe.cpp', output / 'probe.cpp.o'
compile_file(probe_source, probe_obj)
probe_command = list(command)
probe_command[probe_command.index(str(root / 'window-quantization/main.cpp.o'))] = str(root / 'window-quantization/contract-entry.cpp.o')
probe_command.insert(1, str(probe_obj))
records = {}
for name, runtime, flags, expected in [('baseline', archive_old, ['baseline'], 'BASELINE_ES_EMPTY_TITLE_DIRECTORY_REPRODUCED'),
        ('corrected', archive, [], 'NAND_TITLE_HIERARCHY_COMPONENT_PASS')]:
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
(output / 'build.json').write_text(json.dumps({'result': 'NAND_HIERARCHY_COMPONENT_PASS_BOOT_UNVERIFIED',
    'baseBuildSha256': sha(base_path), 'compiled': compiled, 'archiveSha256': sha(archive), 'executableSha256': sha(exe),
    'linkCommand': command, 'records': records, 'probeObjectSha256': sha(probe_obj),
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), public / 'stock_nand_hierarchy_patch.py',
        public / 'stock_nand_paths.h', public / 'stock_nand_hierarchy.inc', public / 'stock_es_title_directory.inc',
        public / 'stock_fs_commands.inc', probe_source]},
    'retainedRuntimeMembers': retained, 'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file()
        and Path(arg).suffix in ('.o', '.a') and arg != str(archive)},
    'sources': ['https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/IOS/ES/ES.cpp'],
    'limits': ['Existing session-only synthetic NAND; no persistent save, UID/permissions, NAND crypto/timing fidelity.',
        'ES path from requested title; mounted active-game path from existing Config game ID, not hardcoded Store asset.',
        'No live profile completion, rendering fidelity or physical Wii oracle claim from component PASS.']}, indent=2) + '\n')
print('NAND_HIERARCHY_COMPONENT_PASS_BOOT_UNVERIFIED retained runtime', len(retained))

"""Build a private persistent-title-data candidate in the existing Wii FSDevice."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile

from build_stock_hidden_input import sha, validate as validate_hidden_input
from stock_vnand_persistence_patch import adapt_source, adapt_rename


def run(command, cwd, log):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=180)
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 0, (command, result.stderr[-4000:])


def validate(path):
    build = json.loads(path.read_text())
    assert build['result'] == 'PRIVATE_VNAND_PERSISTENCE_BUILT_NOT_GAME_VERIFIED'
    assert path.parent.parent == Path('/private/tmp')
    assert path.parent.name.startswith('openshsm-vnand-persist-')
    parent_path = Path(build['parentBuildPath'])
    assert sha(parent_path) == build['parentBuildSha256']
    validate_hidden_input(parent_path)
    parent = json.loads(parent_path.read_text())
    for dependency, digest in build['dependencies'].items():
        assert sha(dependency) == digest, dependency
    original = Path(build['originalSourcePath'])
    assert sha(original) == build['originalSourceSha256']
    assert Path(build['sourcePath']).read_text() == adapt_source(original.read_text())
    rename_original = Path(__file__).with_name('stock_fs_rename.inc')
    assert Path(build['renamePath']).read_text() == adapt_rename(rename_original.read_text())
    for name in ('source', 'rename', 'object', 'archive', 'executable'):
        assert sha(build[name + 'Path']) == build[name + 'Sha256']
    old_members = subprocess.check_output(['/usr/bin/ar', '-t', parent['archivePath']], text=True).splitlines()
    new_members = subprocess.check_output(['/usr/bin/ar', '-t', build['archivePath']], text=True).splitlines()
    assert set(old_members) == set(new_members)
    for name in old_members:
        if name.startswith('__.'):
            continue
        data = subprocess.check_output(['/usr/bin/ar', '-p', build['archivePath'], name])
        expected = build['objectSha256'] if name == 'fs_device.cpp.o' else hashlib.sha256(
            subprocess.check_output(['/usr/bin/ar', '-p', parent['archivePath'], name])).hexdigest()
        assert hashlib.sha256(data).hexdigest() == expected, name
    expected_link = list(parent['linkCommand'])
    expected_link[expected_link.index(parent['archivePath'])] = build['archivePath']
    expected_link[expected_link.index('-o') + 1] = build['executablePath']
    assert build['linkCommand'] == expected_link
    return Path(build['executablePath'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--hidden-input-build', required=True, type=Path)
    args = parser.parse_args()
    parent_path = args.hidden_input_build.resolve()
    validate_hidden_input(parent_path)
    parent = json.loads(parent_path.read_text())
    sysconf_path = Path('/private/tmp/openshsm-sysconf-build-1hz54b5b/build.json')
    sysconf = json.loads(sysconf_path.read_text())
    original = Path(sysconf['sourcePath'])
    assert sha(original) == sysconf['sourceSha256']
    member = subprocess.check_output(['/usr/bin/ar', '-p', parent['archivePath'], 'fs_device.cpp.o'])
    assert hashlib.sha256(member).hexdigest() == sysconf['objectSha256']

    cache = Path(tempfile.mkdtemp(prefix='openshsm-vnand-persist-', dir='/private/tmp'))
    source = cache / 'fs_device.cpp'
    obj = cache / 'fs_device.cpp.o'
    source.write_text(adapt_source(original.read_text()))
    for name in ('stock_sysconf.h', 'stock_fs_rename_commands.inc'):
        shutil.copyfile(original.parent / name, cache / name)
    rename_original = Path(__file__).with_name('stock_fs_rename.inc')
    rename = cache / 'stock_fs_rename.inc'
    rename.write_text(adapt_rename(rename_original.read_text()))
    command = list(sysconf['compileCommand'])
    command[1:1] = ['-I', str(cache)]
    command[command.index(str(original))] = str(source)
    command[command.index('-o') + 1] = str(obj)
    root = Path(__file__).resolve().parents[2] / 'work/private-game/static-recomp/stock-baseline/export/build'
    run(command, root, cache / 'compile.log')

    archive = cache / 'libnwiiruntime.a'
    shutil.copyfile(parent['archivePath'], archive)
    run(['/usr/bin/ar', 'r', str(archive), str(obj)], root, cache / 'archive.log')
    run(['/usr/bin/ranlib', str(archive)], root, cache / 'ranlib.log')
    assert hashlib.sha256(subprocess.check_output(
        ['/usr/bin/ar', '-p', str(archive), obj.name])).hexdigest() == sha(obj)
    link = list(parent['linkCommand'])
    link[link.index(parent['archivePath'])] = str(archive)
    exe = cache / 'OpenSHSMHiddenInput'
    link[link.index('-o') + 1] = str(exe)
    run(link, root, cache / 'link.log')
    report = {'result': 'PRIVATE_VNAND_PERSISTENCE_BUILT_NOT_GAME_VERIFIED',
        'parentBuildPath': str(parent_path), 'parentBuildSha256': sha(parent_path),
        'sysconfBuildPath': str(sysconf_path), 'sysconfBuildSha256': sha(sysconf_path),
        'originalSourcePath': str(original), 'originalSourceSha256': sha(original),
        'sourcePath': str(source), 'sourceSha256': sha(source),
        'renamePath': str(rename), 'renameSha256': sha(rename),
        'objectPath': str(obj), 'objectSha256': sha(obj),
        'archivePath': str(archive), 'archiveSha256': sha(archive),
        'executablePath': str(exe), 'executableSha256': sha(exe),
        'compileCommand': command, 'linkCommand': link,
        'dependencies': {str(path): sha(path) for path in (
            Path(__file__), Path(__file__).with_name('stock_vnand_persistence_patch.py'),
            Path(__file__).with_name('stock_vnand_persistence.h'), rename_original,
            original, original.parent / 'stock_sysconf.h',
            original.parent / 'stock_fs_rename_commands.inc', parent_path, sysconf_path)},
        'limits': ['Private PC adaptation of the existing process-local FSDevice registry.',
            'Only supported R5WEA4 title data is snapshotted; Wii NAND timing and permissions are not claimed.',
            'Normal executable and original game assets remain unchanged.']}
    path = cache / 'build.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    validate(path)
    print(report['result'], path, flush=True)


if __name__ == '__main__':
    main()

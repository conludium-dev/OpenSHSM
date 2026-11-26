"""Correct the current FS producer; retain the current game pipeline and verify native SDK reads."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from stock_sysconf_patch import adapt


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def execute(command, cwd, log):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=60)
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 0, (result.returncode, result.stdout[-1000:], result.stderr[-4000:])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--original-proof', type=Path, required=True)
    args = parser.parse_args()
    public = Path(__file__).resolve().parent
    root = public.parents[1] / 'work/private-game/static-recomp/stock-baseline'
    parent = json.loads(args.parent.read_text())
    assert sha(parent['executablePath']) == parent['executableSha256']
    proof = json.loads(args.original_proof.read_text())
    assert proof['result'] == 'ORIGINAL_WII_SYSCONF_PARSER_ASPECT_CHAIN_PASS' and proof['suppliedServiceHooks'] == 0
    for path, digest in proof['dependencies'].items():
        assert sha(path) == digest
    original = root / 'window-fs-rename/fs_device.cpp'
    record_path = original.parent / 'build.json'
    record = json.loads(record_path.read_text())
    assert sha(original) == record['sourceSha256']
    command = list(parent['linkCommand'])
    old_archive = Path(parent['archivePath'])
    assert sha(old_archive) == parent['archiveSha256']
    before = subprocess.check_output(['/usr/bin/ar', '-p', str(old_archive), 'fs_device.cpp.o'])
    assert hashlib.sha256(before).hexdigest() == record['objectSha256']
    cache = Path(tempfile.mkdtemp(prefix='openshsm-sysconf-build-', dir='/private/tmp'))
    source = cache / 'fs_device.cpp'
    source.write_text(adapt(original.read_text()))
    for header in ('stock_sysconf.h',):
        shutil.copy2(public / header, cache / header)
    shutil.copy2(original.parent / 'stock_fs_rename_commands.inc', cache / 'stock_fs_rename_commands.inc')
    arguments = json.loads((root / 'input-snapshot-research/build.json').read_text())['arguments']
    compiler = '/Library/Developer/CommandLineTools/usr/bin/c++'
    obj = cache / 'fs_device.cpp.o'
    compile_command = [compiler, '-H', *arguments, '-c', str(source), '-o', str(obj)]
    execute(compile_command, root / 'export/build', cache / 'compile.log')
    assert str(cache / 'stock_sysconf.h') in (cache / 'compile.log').read_text()
    archive = cache / old_archive.name
    shutil.copy2(old_archive, archive)
    subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], check=True, capture_output=True)
    subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
    retained = {}
    for member in subprocess.check_output(['/usr/bin/ar', 't', str(old_archive)], text=True).splitlines():
        if member.startswith('__.SYMDEF') or member == obj.name:
            continue
        previous = subprocess.check_output(['/usr/bin/ar', '-p', str(old_archive), member])
        assert previous == subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
        retained[member] = hashlib.sha256(previous).hexdigest()
    command[command.index(str(old_archive))] = str(archive)
    exe = cache / 'OpenSHSM-0.0.42'
    command[command.index('-o') + 1] = str(exe)
    execute(command, root / 'export/build', cache / 'link.log')
    probe = public / 'stock_sysconf_fs_probe.cpp'
    probe_obj = cache / 'probe.cpp.o'
    execute([compiler, *arguments, '-c', str(probe), '-o', str(probe_obj)], root / 'export/build', cache / 'probe-compile.log')
    probe_command = list(command)
    main_obj = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
    probe_command[probe_command.index(main_obj)] = str(root / 'window-quantization/contract-entry.cpp.o')
    probe_command.insert(1, str(probe_obj))
    probe_exe = cache / 'probe'
    probe_command[probe_command.index('-o') + 1] = str(probe_exe)
    execute(probe_command, root / 'export/build', cache / 'probe-link.log')
    dol = public.parents[1] / 'work/private-game/disc/DATA/sys/main.dol'
    prepared = cache / 'prepared-SYSCONF'
    run = execute([str(probe_exe), str(dol), str(prepared)], root / 'export/build', cache / 'probe-run.log')
    assert 'EXISTING_FS_NATIVE_ORIGINAL_PARSER_WIDESCREEN_BYTE_PASS' in run.stdout
    assert prepared.stat().st_size == 0x4000
    report = {'result': 'SYSCONF_EXISTING_FS_NATIVE_CHAIN_COMPILED_LINKED_NOT_LIVE_VERIFIED',
        'parentBuildPath': str(args.parent.resolve()), 'parentBuildSha256': sha(args.parent),
        'originalProofPath': str(args.original_proof.resolve()), 'originalProofSha256': sha(args.original_proof),
        'sourcePath': str(source), 'sourceSha256': sha(source), 'objectSha256': sha(obj),
        'originalSourcePath': str(original), 'originalSourceSha256': sha(original),
        'originalObjectSha256': record['objectSha256'], 'archivePath': str(archive), 'archiveSha256': sha(archive),
        'executablePath': str(exe), 'executableSha256': sha(exe), 'compileCommand': compile_command,
        'linkCommand': command, 'retainedRuntimeMembers': retained,
        'retainedLinkInputs': {arg: sha(arg) for arg in command if Path(arg).is_file()
            and Path(arg).suffix in ('.o', '.a') and arg != str(archive)},
        'nativeProbe': {'linkCommand': probe_command, 'executablePath': str(probe_exe),
            'executableSha256': sha(probe_exe), 'output': run.stdout.strip(),
            'preparedSysconfPath': str(prepared), 'preparedSysconfSha256': sha(prepared)},
        'dependencies': {str(path): sha(path) for path in [Path(__file__), public / 'stock_sysconf_patch.py',
            public / 'stock_sysconf.h', probe, dol, record_path, original.parent / 'stock_fs_rename_commands.inc']},
        'limits': ['PC console default selects original16:9 via validIPL.AR byte, not a forcedcamera/hook.',
            'Onlyoneentry syntheticSYSCONF; allother missingkey default behavior remains original but unverified live.',
            'No startupasyncIOS/fullscene16:9/UI/video/audio/performance acceptance from native component.',
            'Existing saves remain RAM-only; current running game not changed.']}
    path = cache / 'build.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, flush=True)


if __name__ == '__main__':
    main()

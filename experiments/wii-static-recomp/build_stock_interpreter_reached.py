"""Build and compare the exact retained fallback; never overwrite its source or archive."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import tempfile
from stock_interpreter_reached_ops import adapt


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, cwd, log):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=60)
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-5000:]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--play', type=Path, required=True)
    args = parser.parse_args()
    public = Path(__file__).resolve().parent
    root = public.parents[1] / 'work/private-game/static-recomp/stock-baseline'
    parent = json.loads(args.parent.read_text())
    assert sha(parent['executablePath']) == parent['executableSha256']
    play = json.loads((args.play / 'result.json').read_text())
    assert play['psqBuildSha256'] == sha(args.parent)
    assert play['executableSha256'] == parent['executableSha256']
    logs = [args.play / 'runtime-prefix.log', args.play / 'runtime-tail.log']
    log_text = ''.join(path.read_text() for path in logs)
    dol_path = public.parents[1] / 'work/private-game/disc/DATA/sys/main.dol'
    assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
    dol = dol_path.read_bytes()
    layout = struct.unpack('>64I', dol[:256])
    sites = []
    for address, word in ((0x801ef9c0, 0x7cc4006e), (0x8038d750, 0x7c660010),
            (0x8038d758, 0x7c072910)):
        index = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
        assert struct.unpack_from('>I', dol, layout[index] + address - layout[18 + index])[0] == word
        message = f'[Interp] Unhandled op31 xo={(word >> 1) & 1023} at 0x{address:x} (nop)'
        count = log_text.count(message)
        assert count > 0
        sites.append({'address': address, 'opcode': word, 'retainedLogOccurrences': count})
    source = root / 'interpreter-addze-corrected/interpreter.cpp'
    obj = source.with_suffix('.cpp.o')
    old = json.loads((source.parent / 'build.json').read_text())
    assert sha(source) == old['runtime']['sourceSha256']
    assert sha(obj) == old['runtime']['objectSha256']
    command = list(parent['linkCommand'])
    archive = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
    member = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), obj.name])
    assert hashlib.sha256(member).hexdigest() == sha(obj)
    cache = Path(tempfile.mkdtemp(prefix='openshsm-reached-interpreter-', dir='/private/tmp'))
    patched = cache / 'interpreter.cpp'
    patched.write_text(adapt(source.read_text()))
    arguments = json.loads((root / 'window-fp-guard/build.json').read_text())['interpreterArguments']
    compiler = '/Library/Developer/CommandLineTools/usr/bin/c++'
    new_obj = cache / obj.name
    compile_command = [compiler, *arguments, '-c', str(patched), '-o', str(new_obj)]
    run(compile_command, root / 'export/build', cache / 'compile.log')
    new_archive = cache / archive.name
    shutil.copy2(archive, new_archive)
    subprocess.run(['/usr/bin/ar', 'r', str(new_archive), str(new_obj)], check=True, capture_output=True)
    subprocess.run(['/usr/bin/ranlib', str(new_archive)], check=True, capture_output=True)
    retained = {}
    for name in subprocess.check_output(['/usr/bin/ar', 't', str(archive)], text=True).splitlines():
        if name == obj.name or name.startswith('__.SYMDEF'):
            continue
        before = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), name])
        assert before == subprocess.check_output(['/usr/bin/ar', '-p', str(new_archive), name])
        retained[name] = hashlib.sha256(before).hexdigest()
    command[command.index(str(archive))] = str(new_archive)
    exe = cache / 'OpenSHSM-0.0.42'
    command[command.index('-o') + 1] = str(exe)
    run(command, root / 'export/build', cache / 'link.log')
    probe = public / 'stock_interpreter_reached_probe.cpp'
    probe_obj = cache / 'probe.cpp.o'
    run([compiler, *arguments, '-c', str(probe), '-o', str(probe_obj)],
        root / 'export/build', cache / 'probe-compile.log')
    main_obj = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
    probes = {}
    for name, runtime in [('baseline', archive), ('candidate', new_archive)]:
        probe_command = list(command)
        probe_command[probe_command.index(main_obj)] = str(root / 'window-quantization/contract-entry.cpp.o')
        probe_command[probe_command.index(str(new_archive))] = str(runtime)
        probe_command.insert(1, str(probe_obj))
        probe_exe = cache / (name + '-probe')
        probe_command[probe_command.index('-o') + 1] = str(probe_exe)
        run(probe_command, root / 'export/build', cache / (name + '-link.log'))
        probes[name] = {'path': str(probe_exe), 'sha256': sha(probe_exe), 'linkCommand': probe_command}
    report = {'result': 'REACHED_INTERPRETER_CANDIDATE_COMPILED_NOT_EXECUTION_VERIFIED',
        'parentBuildPath': str(args.parent.resolve()), 'parentBuildSha256': sha(args.parent),
        'sourcePath': str(patched), 'sourceSha256': sha(patched), 'objectSha256': sha(new_obj),
        'originalSourcePath': str(source), 'originalSourceSha256': sha(source),
        'originalObjectSha256': sha(obj), 'archivePath': str(new_archive), 'archiveSha256': sha(new_archive),
        'executablePath': str(exe), 'executableSha256': sha(exe), 'sites': sites, 'probes': probes,
        'retainedRuntimeMembers': retained, 'compileCommand': compile_command, 'linkCommand': command,
        'retainedLinkInputs': {arg: sha(arg) for arg in command if Path(arg).is_file()
            and Path(arg).suffix in ('.o', '.a') and arg != str(new_archive)},
        'dependencies': {str(path): sha(path) for path in [Path(__file__), probe,
            public / 'stock_interpreter_reached_ops.py', dol_path, *logs, args.play / 'result.json']},
        'limits': ['Observed lwzux/subfc/subfe omissions only; non-OE carry forms.',
            'Invalid lwzux encodings refuse; original program exception routing remains unverified.',
            'No game launch, graphics/performance improvement or hardware acceptance from compilation.']}
    path = cache / 'build.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, flush=True)


if __name__ == '__main__':
    main()

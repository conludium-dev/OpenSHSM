"""Build one reusable private timed-input derivative of the hidden GL candidate."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile

from stock_hidden_gl_validation import validate as validate_hidden
from stock_hidden_input_patch import adapt


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, cwd, log):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=180)
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 0, (command, result.stderr[-4000:])


def validate(path):
    build = json.loads(path.read_text())
    assert build['result'] == 'PRIVATE_HIDDEN_INPUT_BUILT_NOT_GAME_VERIFIED'
    assert path.parent.parent == Path('/private/tmp')
    assert path.parent.name.startswith('openshsm-hidden-input-')
    parent_path = Path(build['parentBuildPath'])
    assert sha(parent_path) == build['parentBuildSha256']
    validate_hidden(parent_path)
    for dep, digest in build['dependencies'].items():
        assert sha(dep) == digest, dep
    pause = json.loads(Path(build['pauseBuildPath']).read_text())
    row = pause['replacements']['mouse_keyboard_source.cpp.o']
    assert sha(row['sourcePath']) == row['sourceSha256']
    assert adapt(Path(row['sourcePath']).read_text()) == Path(build['sourcePath']).read_text()
    for name in ('source', 'object', 'archive', 'executable'):
        assert sha(build[name + 'Path']) == build[name + 'Sha256']
    archive = Path(build['archivePath'])
    expected_members = {**pause['retainedMembers'],
        **{name: row['objectSha256'] for name, row in pause['replacements'].items()}}
    expected_members['mouse_keyboard_source.cpp.o'] = build['objectSha256']
    member_names = [name for name in subprocess.check_output(
        ['/usr/bin/ar', '-t', str(archive)], text=True).splitlines()
        if not name.startswith('__.')]
    assert set(member_names) == set(expected_members)
    for name in member_names:
        member = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), name])
        assert hashlib.sha256(member).hexdigest() == expected_members[name], name
    expected_link = list(json.loads(parent_path.read_text())['linkCommand'])
    expected_link[expected_link.index(pause['archivePath'])] = str(archive)
    expected_link[expected_link.index('-o') + 1] = build['executablePath']
    assert build['linkCommand'] == expected_link
    assert b'OpenSHSM BUILD 0.0.42\0' in Path(build['executablePath']).read_bytes()
    return Path(build['executablePath'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--hidden-build', required=True, type=Path)
    args = parser.parse_args()
    parent_path = args.hidden_build.resolve()
    validate_hidden(parent_path)
    parent = json.loads(parent_path.read_text())
    pause_path = Path(parent['pauseBuildPath'])
    pause = json.loads(pause_path.read_text())
    row = pause['replacements']['mouse_keyboard_source.cpp.o']
    original = Path(row['sourcePath'])
    assert sha(original) == row['sourceSha256']

    cache = Path(tempfile.mkdtemp(prefix='openshsm-hidden-input-', dir='/private/tmp'))
    source = cache / 'mouse_keyboard_source.cpp'
    obj = cache / 'mouse_keyboard_source.cpp.o'
    source.write_text(adapt(original.read_text()))
    compile_command = list(row['compileCommand'])
    compile_command[compile_command.index(str(original))] = str(source)
    compile_command[compile_command.index('-o') + 1] = str(obj)
    root = Path(__file__).resolve().parents[2] / 'work/private-game/static-recomp/stock-baseline/export/build'
    run(compile_command, root, cache / 'compile.log')

    archive = cache / 'libnwiiruntime.a'
    shutil.copyfile(pause['archivePath'], archive)
    run(['/usr/bin/ar', 'r', str(archive), str(obj)], root, cache / 'archive.log')
    run(['/usr/bin/ranlib', str(archive)], root, cache / 'ranlib.log')
    member = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), obj.name])
    assert hashlib.sha256(member).hexdigest() == sha(obj)
    link = list(parent['linkCommand'])
    link[link.index(pause['archivePath'])] = str(archive)
    exe = cache / 'OpenSHSMHiddenInput'
    link[link.index('-o') + 1] = str(exe)
    run(link, root, cache / 'link.log')

    report = {'result': 'PRIVATE_HIDDEN_INPUT_BUILT_NOT_GAME_VERIFIED',
        'parentBuildPath': str(parent_path), 'parentBuildSha256': sha(parent_path),
        'pauseBuildPath': str(pause_path), 'pauseBuildSha256': sha(pause_path),
        'originalSourcePath': str(original), 'originalSourceSha256': sha(original),
        'sourcePath': str(source), 'sourceSha256': sha(source),
        'objectPath': str(obj), 'objectSha256': sha(obj),
        'archivePath': str(archive), 'archiveSha256': sha(archive),
        'executablePath': str(exe), 'executableSha256': sha(exe),
        'compileCommand': compile_command, 'linkCommand': link,
        'dependencies': {str(p): sha(p) for p in (Path(__file__),
            Path(__file__).with_name('stock_hidden_input_patch.py'), parent_path,
            pause_path, original)},
        'limits': ['Opt-in timing schedule only while OPENSHSM_HIDDEN_GL=1.',
            'Changes only the private input archive member; no normal build/input change.',
            'Button-script execution is a PC diagnostic adaptation, not original Wii input behavior.']}
    path = cache / 'build.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    validate(path)
    print(report['result'], path, flush=True)


if __name__ == '__main__':
    main()

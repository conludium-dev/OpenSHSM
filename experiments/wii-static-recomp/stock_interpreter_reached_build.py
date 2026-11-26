"""Validate a single-member fallback derivative of the current PSQ build."""
from pathlib import Path
import hashlib
import json
import subprocess
from stock_interpreter_reached_ops import adapt


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate(path, parent_path, parent):
    build = json.loads(path.read_text())
    assert build['result'] == 'REACHED_INTERPRETER_CANDIDATE_COMPILED_NOT_EXECUTION_VERIFIED'
    assert Path(build['parentBuildPath']) == parent_path and build['parentBuildSha256'] == sha(parent_path)
    component_path = path.parent / 'verification.json'
    component = json.loads(component_path.read_text())
    assert component['result'] == 'REACHED_INTERPRETER_750CL_COMPONENT_PASS'
    assert component['buildSha256'] == sha(path) and component['candidateMismatchCount'] == 0
    assert component['baselineMismatchCount'] > 0 and component['cases'] >= 8368
    assert component['verifierSha256'] == sha(Path(__file__).with_name('verify_stock_interpreter_reached.py'))
    for row in component['runs'].values():
        assert sha(row['logPath']) == row['logSha256']
    for file, digest in {**build['dependencies'], **build['retainedLinkInputs']}.items():
        assert sha(file) == digest, file
    original = Path(build['originalSourcePath'])
    patched = Path(build['sourcePath'])
    assert sha(original) == build['originalSourceSha256']
    assert patched.read_text() == adapt(original.read_text()) and sha(patched) == build['sourceSha256']
    new_obj = path.parent / 'interpreter.cpp.o'
    assert sha(new_obj) == build['objectSha256']
    compile_command = build['compileCommand']
    assert compile_command[-4:] == ['-c', str(patched), '-o', str(new_obj)]
    root = Path(__file__).resolve().parents[2] / 'work/private-game/static-recomp/stock-baseline'
    arguments = json.loads((root / 'window-fp-guard/build.json').read_text())['interpreterArguments']
    assert compile_command == ['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
        '-c', str(patched), '-o', str(new_obj)]
    original_archive = next(Path(arg) for arg in parent['linkCommand'] if Path(arg).name == 'libnwiiruntime.a')
    archive = Path(build['archivePath'])
    assert sha(archive) == build['archiveSha256']
    names = subprocess.check_output(['/usr/bin/ar', 't', str(original_archive)], text=True).splitlines()
    assert names == subprocess.check_output(['/usr/bin/ar', 't', str(archive)], text=True).splitlines()
    retained = {}
    for name in names:
        if name.startswith('__.SYMDEF'):
            continue
        before = subprocess.check_output(['/usr/bin/ar', '-p', str(original_archive), name])
        after = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), name])
        if name == 'interpreter.cpp.o':
            assert hashlib.sha256(before).hexdigest() == build['originalObjectSha256']
            assert hashlib.sha256(after).hexdigest() == build['objectSha256']
        else:
            assert before == after
            retained[name] = hashlib.sha256(after).hexdigest()
    assert retained == build['retainedRuntimeMembers']
    exe = Path(build['executablePath'])
    assert exe.parent == path.parent and exe.name == 'OpenSHSM-0.0.42'
    expected = list(parent['linkCommand'])
    expected[expected.index(str(original_archive))] = str(archive)
    expected[expected.index('-o') + 1] = str(exe)
    assert expected == build['linkCommand']
    assert sha(exe) == build['executableSha256']
    assert b'OpenSHSM BUILD 0.0.42\0' in exe.read_bytes()
    return exe

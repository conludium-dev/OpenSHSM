"""Validate diagnostic attachment to the exact current DSP producer before launch."""
from pathlib import Path
import hashlib
import json
import subprocess
from stock_dsp_capture_patch import adapt


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate(path, parent_path, parent):
    build = json.loads(path.read_text())
    assert build['result'] == 'BOUNDED_DSP_CAPTURE_CURRENT_RUNTIME_COMPONENT_PASS_NOT_LIVE_VERIFIED'
    assert Path(build['parentBuildPath']) == parent_path and build['parentBuildSha256'] == sha(parent_path)
    for file, digest in {**build['dependencies'], **build['retainedLinkInputs']}.items():
        assert sha(file) == digest, file
    proof_path = Path(build['componentPath'])
    assert sha(proof_path) == build['componentSha256']
    proof = json.loads(proof_path.read_text())
    assert proof['result'] == 'BOUNDED_DSP_CAPTURE_COMPONENT_PASS'
    for file, digest in proof['dependencies'].items():
        assert sha(file) == digest, file
    assert build['runs']['baseline']['output'] == build['runs']['disabled']['output'] == build['runs']['enabled']['output']
    assert 'CURRENT_DSP_MAIL_ACK_WITHOUT_LIST_EXECUTION_REPRODUCED' in build['runs']['enabled']['output']
    for name, row in build['runs'].items():
        assert sha(path.parent / (name + '-probe')) == row['executableSha256']
    original = Path(build['originalSourcePath'])
    source = Path(build['sourcePath'])
    assert sha(original) == build['originalSourceSha256']
    assert source.read_text() == adapt(original.read_text()) and sha(source) == build['sourceSha256']
    public = Path(__file__).resolve().parent
    root = public.parents[1] / 'work/private-game/static-recomp/stock-baseline'
    assert sha(path.parent / 'stock_dsp_capture.h') == sha(public / 'stock_dsp_capture.h')
    for name in ('stock_axwii_commands.h', 'stock_axwii_pb.h'):
        assert sha(path.parent / name) == sha(public / name)
    assert sha(path.parent / 'stock_adma_output.h') == sha(original.parent / 'stock_adma_output.h')
    obj = path.parent / 'hw_dsp.cpp.o'
    assert sha(obj) == build['objectSha256']
    full = json.loads((root / 'window-quantization/build.json').read_text())
    args = next(row['arguments'] for row in full['compiled'] if row['source'] == 'hw_dsp.cpp')
    assert build['compileCommand'] == ['/Library/Developer/CommandLineTools/usr/bin/c++', '-H',
        '-I', str(original.parent / 'include'), *args, '-c', str(source), '-o', str(obj)]
    assert str(path.parent / 'stock_dsp_capture.h') in (path.parent / 'compile.log').read_text()
    for name in ('stock_axwii_commands.h', 'stock_axwii_pb.h'):
        assert str(path.parent / name) in (path.parent / 'compile.log').read_text()
    previous = Path(parent['archivePath'])
    assert sha(previous) == parent['archiveSha256']
    archive = Path(build['archivePath'])
    assert sha(archive) == build['archiveSha256']
    names = subprocess.check_output(['/usr/bin/ar', 't', str(previous)], text=True).splitlines()
    assert names == subprocess.check_output(['/usr/bin/ar', 't', str(archive)], text=True).splitlines()
    retained = {}
    for name in names:
        if name.startswith('__.SYMDEF'):
            continue
        before = subprocess.check_output(['/usr/bin/ar', '-p', str(previous), name])
        after = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), name])
        if name == 'hw_dsp.cpp.o':
            assert hashlib.sha256(before).hexdigest() == build['originalObjectSha256']
            assert hashlib.sha256(after).hexdigest() == build['objectSha256']
        else:
            assert before == after
            retained[name] = hashlib.sha256(after).hexdigest()
    assert retained == build['retainedRuntimeMembers']
    exe = Path(build['executablePath'])
    expected = list(parent['linkCommand'])
    expected[expected.index(str(previous))] = str(archive)
    expected[expected.index('-o') + 1] = str(exe)
    assert exe.parent == path.parent and exe.name == 'OpenSHSM-0.0.42'
    assert expected == build['linkCommand'] and sha(exe) == build['executableSha256']
    return exe

"""Validate the sole DSP-member AX derivative against the current font/runtime chain."""
from pathlib import Path
import json
import subprocess
from stock_debug_font_build import sha
from stock_axwii_device_patch import adapt


def validate(path, parent_path, parent, dsp_path):
    build = json.loads(path.read_text())
    assert build['result'] == 'AXWII_DEVICE_CURRENT_DSP_COMPILED_NOT_LIVE_VERIFIED'
    assert Path(build['parentBuildPath']) == parent_path and build['parentBuildSha256'] == sha(parent_path)
    assert Path(build['dspBuildPath']) == dsp_path and build['dspBuildSha256'] == sha(dsp_path)
    dsp = json.loads(dsp_path.read_text())
    for file, digest in {**build['dependencies'], **build['retainedLinkInputs']}.items():
        assert sha(file) == digest, file
    proof_path = Path(build['componentPath'])
    assert sha(proof_path) == build['componentSha256']
    proof = json.loads(proof_path.read_text())
    assert proof['result'] == 'CURRENT_AXWII_DEVICE_MMIO_PCM_PASS_NOT_GAME_AUDIO'
    assert set(proof['guards']) == {'disabled', 'firmware', 'coefficients', 'address'}
    assert sha(proof_path.parent / 'probe') == proof['executableSha256']
    for file, digest in proof['dependencies'].items():
        assert sha(file) == digest, file
    source, obj = Path(build['sourcePath']), Path(build['objectPath'])
    assert source.parent == path.parent and obj.parent == path.parent
    assert source.read_text() == adapt(Path(dsp['sourcePath']).read_text())
    assert sha(source) == build['sourceSha256'] == proof['sourceSha256']
    assert sha(obj) == build['objectSha256']
    public = Path(__file__).resolve().parent
    for name in build['copiedHeaders']:
        original = dsp_path.parent / name if name in ('stock_dsp_capture.h', 'stock_adma_output.h') else public / name
        assert sha(path.parent / name) == sha(original)
        assert str(path.parent / name) in (path.parent / 'compile.log').read_text()
    command = list(dsp['compileCommand'])
    command[command.index(dsp['sourcePath'])] = str(source)
    command[command.index('-o') + 1] = str(obj)
    assert build['compileCommand'] == command
    previous = Path(parent['archivePath'])
    assert str(previous) == dsp['archivePath'] and sha(previous) == parent['archiveSha256'] == dsp['archiveSha256']
    archive = Path(build['archivePath'])
    assert archive.parent == path.parent and sha(archive) == build['archiveSha256']
    names = subprocess.check_output(['/usr/bin/ar', 't', str(previous)], text=True).splitlines()
    assert names == subprocess.check_output(['/usr/bin/ar', 't', str(archive)], text=True).splitlines()
    retained = {}
    for name in names:
        if name.startswith('__.SYMDEF'):
            continue
        before = subprocess.check_output(['/usr/bin/ar', '-p', str(previous), name])
        after = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), name])
        if name == obj.name:
            import hashlib
            assert hashlib.sha256(before).hexdigest() == dsp['objectSha256']
            assert hashlib.sha256(after).hexdigest() == build['objectSha256']
        else:
            assert before == after
            import hashlib
            retained[name] = hashlib.sha256(after).hexdigest()
    assert retained == build['retainedRuntimeMembers']
    exe = Path(build['executablePath'])
    expected = list(parent['linkCommand'])
    expected[expected.index(str(previous))] = str(archive)
    expected[expected.index('-o') + 1] = str(exe)
    assert exe.parent == path.parent and exe.name == 'OpenSHSM-0.0.42'
    assert build['linkCommand'] == expected and sha(exe) == build['executableSha256']
    return exe

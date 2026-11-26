"""Validate the one-object private invisible GL diagnostic derivative."""
from pathlib import Path
import json

from stock_hidden_gl_patch import adapt
from stock_pause_input_validation import validate as validate_pause
from verify_wii_us_copy import digest


def validate(path):
    build = json.loads(path.read_text())
    assert build['result'] == 'PRIVATE_HIDDEN_SILENT_GL_BUILT_NOT_GAME_VERIFIED'
    assert path.parent.parent == Path('/private/tmp')
    assert path.parent.name.startswith('openshsm-hidden-gl-')
    pause_path = Path(build['pauseBuildPath'])
    assert digest(pause_path) == build['pauseBuildSha256']
    pause = json.loads(pause_path.read_text())
    validate_pause(pause_path, Path(pause['rendererBuildPath']),
        Path(pause['rendererGlProofPath']))
    for source, expected in build['dependencies'].items():
        assert digest(Path(source)) == expected, source
    main_path = Path(build['mainBuildPath'])
    assert digest(main_path) == build['mainBuildSha256']
    main = json.loads(main_path.read_text())
    original = Path(build['originalMainPath'])
    source = Path(build['sourcePath'])
    obj = Path(build['objectPath'])
    exe = Path(build['executablePath'])
    assert main['sourcePath'] == str(original)
    assert digest(original) == build['originalMainSha256']
    assert adapt(original.read_text()) == source.read_text()
    assert digest(source) == build['sourceSha256']
    assert digest(obj) == build['objectSha256']
    assert digest(exe) == build['executableSha256']
    original_obj = main['objectPath']
    assert original_obj in pause['linkCommand']
    expected_link = list(pause['linkCommand'])
    expected_link[expected_link.index(original_obj)] = str(obj)
    expected_link[expected_link.index('-o') + 1] = str(exe)
    assert build['linkCommand'] == expected_link
    assert b'OpenSHSM BUILD 0.0.42\0' in exe.read_bytes()
    return exe

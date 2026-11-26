"""Validate the private Wii-1 pause-input derivative before launch."""
from pathlib import Path
import hashlib
import json
import subprocess

from stock_debug_font_build import sha
from stock_gx_renderer_texgen_validation import validate as validate_renderer


def validate(build_path, renderer_path, renderer_gl_proof_path):
    build = json.loads(build_path.read_text())
    assert build['result'] == 'PAUSE_INPUT_PRIVATE_BUILT_NOT_GAME_VERIFIED'
    assert build_path.parent.parent == Path('/private/tmp')
    assert build_path.parent.name.startswith('openshsm-pause-input-')
    assert build['rendererBuildPath'] == str(renderer_path)
    assert build['rendererBuildSha256'] == sha(renderer_path)
    assert build['rendererGlProofPath'] == str(renderer_gl_proof_path)
    assert build['rendererGlProofSha256'] == sha(renderer_gl_proof_path)
    renderer = json.loads(renderer_path.read_text())
    validate_renderer(renderer_path, Path(renderer['parentPath']), renderer_gl_proof_path)
    for path, digest in build['dependencies'].items():
        assert sha(path) == digest, path
    assert set(build['replacements']) == {
        'mouse_keyboard_source.cpp.o', 'gamepad_source.cpp.o', 'input_manager.cpp.o'}
    assert sha(build['headerPath']) == build['headerSha256']
    for row in build['replacements'].values():
        assert sha(row['originalPath']) == row['originalSha256']
        assert sha(row['sourcePath']) == row['sourceSha256']
        assert sha(row['objectPath']) == row['objectSha256']
    archive = Path(build['archivePath'])
    assert archive.parent == build_path.parent and sha(archive) == build['archiveSha256']
    for member, digest in {**build['retainedMembers'],
            **{name: row['objectSha256'] for name, row in build['replacements'].items()}}.items():
        body = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
        assert hashlib.sha256(body).hexdigest() == digest, member
    executable = Path(build['executablePath'])
    assert executable.parent == build_path.parent and sha(executable) == build['executableSha256']
    assert b'OpenSHSM BUILD 0.0.42\0' in executable.read_bytes()
    return executable

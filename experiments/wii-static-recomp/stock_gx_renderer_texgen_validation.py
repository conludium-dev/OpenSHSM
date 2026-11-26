"""Validate a private renderer derivative before a user-owned game run."""
from pathlib import Path
import hashlib
import json
import subprocess
from stock_debug_font_build import sha


def validate(build_path, parent_path, gl_proof_path):
    build = json.loads(build_path.read_text())
    parent = json.loads(parent_path.read_text())
    proof = json.loads(gl_proof_path.read_text())
    assert build['result'] == 'CURRENT_RENDERER_TEXGEN_PRIVATE_BUILT_NOT_GAME_VERIFIED'
    assert proof['result'] == 'CURRENT_RENDERER_TEXGEN_HIDDEN_GL_PASS_NOT_GAME_SCENE'
    assert build_path.parent.parent == Path('/private/tmp')
    assert build_path.parent.name.startswith('openshsm-renderer-texgen-')
    assert Path(build['parentPath']) == parent_path and build['parentSha256'] == sha(parent_path)
    assert proof['candidatePath'] == str(build_path) and proof['candidateSha256'] == sha(build_path)
    assert parent['result'] == 'AXWII_DEVICE_CURRENT_DSP_COMPILED_NOT_LIVE_VERIFIED'
    for report in (build, proof):
        for path, digest in report['dependencies'].items():
            assert sha(path) == digest, path
    assert sha(build['archivePath']) == build['archiveSha256']
    executable = Path(build['executablePath'])
    assert executable.parent == build_path.parent and sha(executable) == build['executableSha256']
    assert b'OpenSHSM BUILD 0.0.42\0' in executable.read_bytes()
    replacements = build['replacements']
    assert set(replacements) == {'fifo_parser.cpp.o', 'renderer_gl.cpp.o', 'tev_shader_gen.cpp.o'}
    for member, digest in {**build['retainedMembers'],
            **{name: row['objectSha256'] for name, row in replacements.items()}}.items():
        body = subprocess.check_output(['/usr/bin/ar', '-p', build['archivePath'], member])
        assert hashlib.sha256(body).hexdigest() == digest, member
    return executable

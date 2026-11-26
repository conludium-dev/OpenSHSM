"""Compare actual diagnostic and guarded OpenGL runs; do not equate GL success with a game screen."""
from pathlib import Path
import hashlib
import json

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
before = root / 'ipc-gldiag'
after = root / 'ipc-glguard'
old = '  if (uProj < 0)\n    return;'
new = '    if (uProj < 0 || s_active_shader.id == 0) {\n        return;\n    }'
text = (before / 'renderer_gl.cpp').read_text()
assert text.count(old) == 1
assert (after / 'renderer_gl.cpp').read_text() == text.replace(old, new)
for name in ('hw_ipc.cpp', 'hw_ai.cpp', 'ios.cpp'):
    assert (before / name).read_bytes() == (after / name).read_bytes()
observations = {}
for variant, directory, exe_name in (
    ('ipc-gldiag', before, 'OpenSHSMStockIPCGLDiag'),
    ('ipc-glguard', after, 'OpenSHSMStockIPCGLGuard'),
):
    build = json.loads((directory / 'build.json').read_text())
    assert sha(directory / 'renderer_gl.cpp') == build['rendererSourceSha256']
    assert sha(directory / exe_name) == build['executableSha256']
    assert sha(root / 'export/build/nWiiRuntime/libnwiiruntime.a') == build['baseArchiveSha256']
    for name, digest in build['retainedObjects'].items():
        assert sha(root / 'export/build' / name) == digest
    label = variant + '-headless-gx-windowed'
    run = json.loads((root / (label + '-result.json')).read_text())
    log = root / (label + '.log')
    assert run['windowed'] and run['gxTrace'] and run['deadlineReached']
    assert run['terminalReturncode'] in (-15, -9)
    assert run['executableSha256'] == build['executableSha256']
    assert run['logSha256'] == sha(log)
    text = log.read_text()
    assert 'Apple M4' in text and '[GXTRACE] draw:' in text
    assert 'linked=1 glErr=0x0' in text
    assert '[ GPU Hang detected ]' in text
    assert 'efb_nonblack=0/307200' in text
    phases = [line for line in text.splitlines() if '[GLPHASE]' in line]
    if variant == 'ipc-gldiag':
        assert '[GLPHASE] before program bind error=0x502' in text
    else:
        assert not phases, phases
    observations[variant] = {'logSha256': sha(log), 'phaseErrors': phases,
        'retainedObjects': len(build['retainedObjects']),
        'unchangedRuntimeObjects': len(build['unchangedRuntimeMembers'])}
(after / 'projection-audit.json').write_text(json.dumps({
    'result': 'PROJECTION_NO_PROGRAM_GUARD_AB_PASS', 'observations': observations,
    'limits': ['Guard corrects host API misuse only; watchdog still fires and EFB remains black.',
        'No original Wii behavior, first-screen, screenshot, input or full-game claim.']
}, indent=2) + '\n')
print('PASS exact renderer guard delta and actual Mac GL A/B; GPU hang and black EFB remain')

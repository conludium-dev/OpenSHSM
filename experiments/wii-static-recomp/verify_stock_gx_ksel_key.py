"""Show that KSel changes generated TEV source despite the retained base hash."""
from pathlib import Path
import argparse
import json
import subprocess
import tempfile

from stock_debug_font_build import sha
from stock_gx_renderer_texgen_validation import validate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--renderer-build', type=Path, required=True)
    parser.add_argument('--renderer-gl-proof', type=Path, required=True)
    args = parser.parse_args()
    build_path = args.renderer_build.resolve()
    build = json.loads(build_path.read_text())
    validate(build_path, Path(build['parentPath']), args.renderer_gl_proof.resolve())
    project = Path(__file__).resolve().parents[2]
    baseline = project / 'work/private-game/static-recomp/stock-baseline/export/nWiiRuntime'
    source = Path(__file__).with_name('stock_gx_ksel_key_probe.cpp')
    tev = baseline / 'src/hle/gx/tev_shader_gen.cpp'
    output = Path(tempfile.mkdtemp(prefix='openshsm-gx-ksel-key-', dir='/private/tmp'))
    exe = output / 'probe'
    command = ['/usr/bin/c++', '-std=c++20', '-I', str(baseline / 'include'),
        str(source), str(tev), '-o', str(exe)]
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (output / 'compile.log').write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0, compiled.stderr[-4000:]
    tested = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
    assert tested.returncode == 0 and 'GX_KSEL_OLD_HASH_COLLISION_CONFIRMED' in tested.stdout
    report = {'result': 'GX_KSEL_BASE_HASH_COLLISION_CONFIRMED_PRIVATE_FIX_BUILT',
        'rendererBuildPath': str(build_path), 'rendererBuildSha256': sha(build_path),
        'rendererGlProofPath': str(args.renderer_gl_proof.resolve()),
        'rendererGlProofSha256': sha(args.renderer_gl_proof),
        'probeSourcePath': str(source), 'probeSourceSha256': sha(source),
        'tevSourcePath': str(tev), 'tevSourceSha256': sha(tev),
        'executableSha256': sha(exe), 'compileCommand': command,
        'output': tested.stdout.strip(),
        'limits': ['The retained GXState base hash collides when F6 KSel changes while actual generated GLSL differs.',
            'Private renderer extends the key; hidden GL confirms separate cache entry and red/green constant-color pixels via BP command routing.',
            'No original scene, visual correction, performance improvement or full TEV fidelity is established.']}
    path = output / 'verification.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, flush=True)


if __name__ == '__main__':
    main()

"""Compare the renderer key with its actual compiled TEV generator, headless."""
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
    proof_path = args.renderer_gl_proof.resolve()
    build = json.loads(build_path.read_text())
    validate(build_path, Path(build['parentPath']), proof_path)
    project = Path(__file__).resolve().parents[2]
    public = Path(__file__).resolve().parent
    root = project / 'work/private-game/static-recomp/stock-baseline'
    source = public / 'stock_gx_shader_key_probe.cpp'
    header = public / 'stock_gx_shader_key.h'
    tev = Path(build['replacements']['tev_shader_gen.cpp.o']['objectPath'])
    assert sha(tev) == build['replacements']['tev_shader_gen.cpp.o']['objectSha256']
    assert build['dependencies'][str(header)] == sha(header)
    output = Path(tempfile.mkdtemp(prefix='openshsm-gx-shader-key-', dir='/private/tmp'))
    exe = output / 'probe'
    command = ['/usr/bin/c++', '-std=c++20', '-I', str(public),
        '-I', str(root / 'headless-tev-banks/include'),
        '-I', str(root / 'export/nWiiRuntime/include'),
        str(source), str(tev), '-o', str(exe)]
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (output / 'compile.log').write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0, compiled.stderr[-4000:]
    tested = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
    (output / 'run.log').write_text(tested.stdout + tested.stderr)
    assert tested.returncode == 0 and 'GX_SEMANTIC_SHADER_KEY_PASS 2048' in tested.stdout, (
        tested.returncode, tested.stdout, tested.stderr)
    report = {'result': 'GX_SEMANTIC_SHADER_KEY_HEADLESS_PASS_NOT_GAME_PERFORMANCE',
        'rendererBuildPath': str(build_path), 'rendererBuildSha256': sha(build_path),
        'rendererGlProofPath': str(proof_path), 'rendererGlProofSha256': sha(proof_path),
        'probeSourcePath': str(source), 'probeSourceSha256': sha(source),
        'keyHeaderPath': str(header), 'keyHeaderSha256': sha(header),
        'tevObjectPath': str(tev), 'tevObjectSha256': sha(tev),
        'executableSha256': sha(exe), 'compileCommand': command,
        'output': tested.stdout.strip(),
        'limits': ['2048 generated TEV states preserve exact vertex and fragment source when only excluded renderer state changes.',
            'Synthetic 256-state blend/texture-format variation produces 256 old keys but one semantic key.',
            'No original late-game draw stream, measured shader compilation reduction or game FPS acceptance.']}
    path = output / 'verification.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, flush=True)


if __name__ == '__main__':
    main()

"""Exercise the private renderer/TEV candidate in a hidden native GL context."""
from pathlib import Path
import argparse
import json
import subprocess
import tempfile
from stock_debug_font_build import sha


def run(command, cwd, log, timeout=120):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 0, (command, result.stderr[-4000:])
    return result.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path, required=True)
    args = parser.parse_args()
    build = json.loads(args.build.read_text())
    assert build['result'] == 'CURRENT_RENDERER_TEXGEN_PRIVATE_BUILT_NOT_GAME_VERIFIED'
    for path, digest in build['dependencies'].items():
        assert sha(path) == digest, path
    assert sha(build['archivePath']) == build['archiveSha256']
    assert sha(build['executablePath']) == build['executableSha256']
    root = Path(__file__).resolve().parents[2]
    baseline = root / 'work/private-game/static-recomp/stock-baseline'
    cache = Path(tempfile.mkdtemp(prefix='openshsm-renderer-texgen-gl-', dir='/private/tmp'))
    probe = Path(__file__).resolve().parent / 'stock_gx_renderer_texgen_gl_probe.cpp'
    object_path = cache / 'probe.o'
    command = list(build['replacements']['fifo_parser.cpp.o']['compileCommand'])
    command[command.index(build['replacements']['fifo_parser.cpp.o']['sourcePath'])] = str(probe)
    command[command.index('-o') + 1] = str(object_path)
    run(command, baseline / 'export/build', cache / 'compile.log')
    link = list(build['linkCommand'])
    main = next(path for path in link if Path(path).name == 'main.cpp.o')
    link[link.index(main)] = str(baseline / 'window-quantization/contract-entry.cpp.o')
    link.insert(1, str(object_path))
    executable = cache / 'probe'
    link[link.index('-o') + 1] = str(executable)
    run(link, baseline / 'export/build', cache / 'link.log', 180)
    output = run([str(executable)], baseline / 'export/build', cache / 'run.log', 30)
    assert 'GX_RENDERER_TEXGEN_GL_PASS 25' in output
    assert 'BP41_COLOR_ALPHA_MASK_GL_PASS 3' in output
    assert 'EFB_COPY_SIZE 4 4 255 0 0' in output
    assert 'EFB_COPY_SIZE 8 8 255 0 0' in output
    assert 'EFB_COPY_PARTIAL 4 4 0 255 255 0' in output
    report = {'result': 'CURRENT_RENDERER_TEXGEN_HIDDEN_GL_PASS_NOT_GAME_SCENE',
        'output': output.strip(), 'candidatePath': str(args.build.resolve()),
        'candidateSha256': sha(args.build), 'executableSha256': sha(executable),
        'compileCommand': command, 'linkCommand': link,
        'dependencies': {str(path.resolve()): sha(path) for path in
            [Path(__file__), args.build, probe, baseline / 'window-quantization/contract-entry.cpp.o']},
        'limits': ['Native hidden GL, actual candidate archive/renderer and generated TEV shader.',
            'Synthetic constant triangle, two UV sources, independent regular texgen fallback when one source is absent, post-lighting color0/color1 texgen via shader uniforms and distinct raw vertex color1 input, projective Q, ordered XF dual-postmatrix, BP scale conversion, unloaded matrix fallback, red/green KColor pixels through BP commands, distinct cache entry for F6 and reused entry for blend-only BP41, BP41 RGB/alpha write masks, independent alpha light mask when color lighting is disabled, BP52 half-scale, partial same-stride RGBA8 update and full-size EFB copies with actual GL dimensions and pixels. No original SHSM draw stream or game pixels.',
            'Color/emboss/absent-source fallback, per-draw XF timing, gameplay graphics/FPS/audio remain unverified.']}
    path = cache / 'verification.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, flush=True)


if __name__ == '__main__':
    main()

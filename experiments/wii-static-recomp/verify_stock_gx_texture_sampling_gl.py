"""Check manual/automatic GX coordinate scale and texture dimensions in actual GL."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
from stock_gx_texture_sampling_patch import shader, renderer
from stock_vertex_sources_patch import adapt_header


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument("--renderer", type=Path, required=True)
    args = parser.parse_args()
    public = Path(__file__).resolve().parent
    root = public.parents[1] / 'work/private-game/static-recomp/stock-baseline'
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    header = output / 'runtime/gx/fifo_parser.h'
    header.parent.mkdir(parents=True, exist_ok=True)
    header.write_text(adapt_header((root / 'export/nWiiRuntime/include/runtime/gx/fifo_parser.h').read_text()))
    recipe_path = root / 'window-pe-execute/build.json'
    recipe = json.loads(recipe_path.read_text())['changes']['renderer_gl.cpp']
    command = list(recipe['compileCommand'])
    command[1:1] = ['-I', str(output)]
    command[command.index('-c') + 1] = str(public / 'stock_gx_texture_sampling_gl_probe.cpp')
    results = {}
    for name, text in [('baseline', args.source.read_text()), ('candidate', shader(args.source.read_text()))]:
        source = output / (name + '.cpp')
        source.write_text(text)
        obj = output / (name + '.o')
        exe = output / name
        renderer_source = output / (name + '-renderer.cpp')
        renderer_source.write_text(args.renderer.read_text() if name == 'baseline' else renderer(args.renderer.read_text()))
        compile_command = list(command)
        compile_command[compile_command.index('-o') + 1] = str(obj)
        compile_command.append('-DOPENSHSM_RENDERER_SOURCE="' + str(renderer_source) + '"')
        compile_command.append('-DOPENSHSM_SHADER_SOURCE="' + str(source) + '"')
        compiled = subprocess.run(compile_command, capture_output=True, text=True, timeout=120)
        (output / (name + '-compile.log')).write_text(compiled.stdout + compiled.stderr)
        assert compiled.returncode == 0, compiled.stderr[-4000:]
        build = root / 'export/build'
        link = [command[0], '-isysroot', command[command.index('-isysroot') + 1],
            str(obj), str(build / '_deps/sdl2-build/libSDL2d.a'),
            str(build / '_deps/glad-build/libglad.a'), '-o', str(exe), '-lm', '-liconv']
        for framework in ['CoreVideo', 'Cocoa', 'IOKit', 'ForceFeedback', 'Carbon',
                'CoreAudio', 'AudioToolbox', 'AVFoundation', 'Foundation',
                'GameController', 'Metal', 'QuartzCore', 'CoreHaptics']:
            link.extend(['-framework', framework])
        linked = subprocess.run(link, capture_output=True, text=True, timeout=120)
        (output / (name + '-link.log')).write_text(linked.stdout + linked.stderr)
        assert linked.returncode == 0, linked.stderr[-4000:]
        run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
        (output / (name + '-run.log')).write_text(run.stdout + run.stderr)
        results[name] = {'exitCode': run.returncode, 'output': run.stdout + run.stderr,
            'sourceSha256': sha(source), 'executableSha256': sha(exe)}
    assert results['baseline']['exitCode'] == 1, results['baseline']
    assert results['candidate']['exitCode'] == 0, results['candidate']
    assert 'TEX_SAMPLING_GL cases=7 failures=0' in results['candidate']['output']
    report = {'result': 'TEX_SAMPLING_ACTUAL_GL_7_PASS_BASELINE_FAIL', 'runs': results,
        'dependencies': {str(path.resolve()): sha(path) for path in [args.source, args.renderer, recipe_path, public / "stock_gx_shader_key.h",
            public / 'stock_gx_texture_sampling_patch.py', public / 'stock_gx_texture_sampling_gl_probe.cpp', Path(__file__)]},
        'limits': ['Actual renderer and generated shaders in real GL; explicit fixture BP writes and unused hardware/texture services.',
            'Checks manual texel coordinates, normalized SU scaling, dynamic texture dimensions and projective Q.',
            'No claim of game cutscene, performance or audio acceptance.']}
    (output / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()

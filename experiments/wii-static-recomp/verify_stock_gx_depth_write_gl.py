"""Check the actual renderer's depth state with fixture-only BP/texture services."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
from stock_gx_renderer_texgen_patch import depth_write
from stock_vertex_sources_patch import adapt_header


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
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
    command[command.index('-c') + 1] = str(public / 'stock_gx_depth_write_gl_probe.cpp')
    results = {}
    for name, text in [('baseline', args.source.read_text()), ('candidate', depth_write(args.source.read_text()))]:
        source = output / (name + '.cpp')
        source.write_text(text)
        obj = output / (name + '.o')
        exe = output / name
        compile_command = list(command)
        compile_command[compile_command.index('-o') + 1] = str(obj)
        compile_command.append('-DOPENSHSM_RENDERER_SOURCE="' + str(source) + '"')
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
    assert 'GX_DEPTH_WRITE_GL checks=2 failures=0' in results['candidate']['output']
    report = {'result': 'GX_DEPTH_WRITE_ACTUAL_GL_2_PASS_BASELINE_FAIL', 'runs': results,
        'dependencies': {str(path.resolve()): sha(path) for path in [args.source, recipe_path,
            public / 'stock_gx_renderer_texgen_patch.py', public / 'stock_gx_depth_write_gl_probe.cpp', Path(__file__)]},
        'limits': ['Actual renderer and real GL depth buffer; fixture BP register writes and clear colour.',
            'Guest shaders, textures, FIFO notifications and game execution are deliberately excluded.',
            'No claim of repaired cutscene image, frame rate or audio.']}
    (output / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()

"""Render the existing overlay with prepared SDL/glad, no guest assets or live game changes."""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    public = Path(__file__).resolve().parent
    root = public.parents[1] / 'work/private-game/static-recomp/stock-baseline/export/build'
    recipe_path = Path('/private/tmp/openshsm-pc-branding-2g4tcfp5/build.json')
    recipe = json.loads(recipe_path.read_text())
    cache = Path(tempfile.mkdtemp(prefix='openshsm-debug-font-gl-', dir='/private/tmp'))
    obj = cache / 'probe.o'
    exe = cache / 'probe'
    image = cache / 'preview.bmp'
    source = public / 'stock_debug_font_gl_probe.cpp'
    command = [*recipe['compileCommand'][:-4], '-c', str(source), '-o', str(obj)]
    command.remove('-H')
    compiled = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=60)
    (cache / 'compile.log').write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0, compiled.stderr
    link = recipe['linkCommand']
    tail = link[link.index('_deps/sdl2-build/libSDL2d.a'):]
    link_command = [command[0], '-isysroot', '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk',
        str(obj), '-o', str(exe), *tail]
    linked = subprocess.run(link_command, cwd=root, capture_output=True, text=True, timeout=60)
    (cache / 'link.log').write_text(linked.stdout + linked.stderr)
    assert linked.returncode == 0, linked.stderr
    run = subprocess.run([str(exe), str(image)], capture_output=True, text=True, timeout=30)
    (cache / 'run.log').write_text(run.stdout + run.stderr)
    assert run.returncode == 0 and 'DEBUG_FONT_REAL_GL_STATE_EFB_PASS' in run.stdout, (run.returncode, run.stdout, run.stderr)
    report = {'result': 'DEBUG_FONT_REAL_GL_COMPONENT_PASS', 'output': run.stdout.strip(),
        'previewPath': str(image), 'previewSha256': sha(image), 'compileCommand': command,
        'linkCommand': link_command, 'executableSha256': sha(exe),
        'dependencies': {str(path): sha(path) for path in [Path(__file__), source,
            public / 'stock_debug_overlay.h', public / 'stock_debug_font.h', recipe_path]},
        'limits': ['Real hidden SDL/OpenGL component, not live game overlay acceptance.',
            'Existing metrics unchanged; no fabricated game-speed percentage.',
            'No game source/assets/profile/current process modified.']}
    path = cache / 'verification.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, image, flush=True)


if __name__ == '__main__':
    main()

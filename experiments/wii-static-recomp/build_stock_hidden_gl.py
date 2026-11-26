"""Build a private invisible, silent GL diagnostic from the verified input candidate."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile

from stock_hidden_gl_patch import adapt
from stock_pause_input_validation import validate as validate_pause


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, cwd, log):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=180)
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 0, (command, result.stderr[-4000:])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pause-input-build', type=Path, required=True)
    args = parser.parse_args()
    pause_path = args.pause_input_build.resolve()
    pause = json.loads(pause_path.read_text())
    validate_pause(pause_path, Path(pause['rendererBuildPath']),
        Path(pause['rendererGlProofPath']))

    main_objects = [Path(item) for item in pause['linkCommand']
        if item.endswith('/main.cpp.o')]
    assert len(main_objects) == 1
    main_object = main_objects[0]
    main_build_path = main_object.parent / 'build.json'
    main_build = json.loads(main_build_path.read_text())
    assert main_build['objectPath'] == str(main_object)
    assert digest(main_object) == main_build['objectSha256']
    original = Path(main_build['sourcePath'])
    assert digest(original) == main_build['sourceSha256']
    assert 'SDL_WINDOW_HIDDEN' in original.read_text()
    assert original.read_text().count('SDL_ShowWindow(window);') == 1

    project = Path(__file__).resolve().parents[2]
    root = project / 'work/private-game/static-recomp/stock-baseline'
    cache = Path(tempfile.mkdtemp(prefix='openshsm-hidden-gl-', dir='/private/tmp'))
    for name in ('BuildVersion.h', 'stock_debug_overlay.h',
                 'stock_debug_font.h', 'stock_first_image.h'):
        shutil.copyfile(original.parent / name, cache / name)
    source = cache / 'main.cpp'
    obj = cache / 'main.cpp.o'
    source.write_text(adapt(original.read_text()))
    command = list(main_build['compileCommand'])
    command[command.index(str(original))] = str(source)
    command[command.index('-o') + 1] = str(obj)
    run(command, root / 'export/build', cache / 'compile.log')

    link = list(pause['linkCommand'])
    link[link.index(str(main_object))] = str(obj)
    exe = cache / 'OpenSHSMHiddenGL'
    link[link.index('-o') + 1] = str(exe)
    run(link, root / 'export/build', cache / 'link.log')
    assert b'OpenSHSM BUILD 0.0.42\0' in exe.read_bytes()

    report = {'result': 'PRIVATE_HIDDEN_SILENT_GL_BUILT_NOT_GAME_VERIFIED',
        'pauseBuildPath': str(pause_path), 'pauseBuildSha256': digest(pause_path),
        'mainBuildPath': str(main_build_path), 'mainBuildSha256': digest(main_build_path),
        'originalMainPath': str(original), 'originalMainSha256': digest(original),
        'sourcePath': str(source), 'sourceSha256': digest(source),
        'objectPath': str(obj), 'objectSha256': digest(obj),
        'executablePath': str(exe), 'executableSha256': digest(exe),
        'compileCommand': command, 'linkCommand': link,
        'dependencies': {str(path): digest(path) for path in
            [Path(__file__).resolve(), Path(__file__).with_name('stock_hidden_gl_patch.py'),
             pause_path, main_build_path,
             *[cache / name for name in ('BuildVersion.h', 'stock_debug_overlay.h',
               'stock_debug_font.h', 'stock_first_image.h')]]},
        'limits': ['Opt-in OPENSHSM_HIDDEN_GL=1 keeps the SDL GL window hidden and skips audio-device opening.',
            'The normal path remains unchanged; visible game and audible acceptance are not implied.',
            'Screenshot cadence becomes 120 presents only in this hidden diagnostic mode.']}
    path = cache / 'build.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, flush=True)


if __name__ == '__main__':
    main()

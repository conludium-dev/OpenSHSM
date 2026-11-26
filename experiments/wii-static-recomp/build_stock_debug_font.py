"""Replace only the current main object's overlay header, retaining the full runtime chain."""
from pathlib import Path
import argparse
import json
import shutil
import tempfile
from build_stock_sysconf import execute
from stock_debug_font_build import sha, validate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--main-build', type=Path, required=True)
    parser.add_argument('--component', type=Path, required=True)
    args = parser.parse_args()
    public = Path(__file__).resolve().parent
    root = public.parents[1] / 'work/private-game/static-recomp/stock-baseline'
    parent_path = args.parent.resolve()
    parent = json.loads(parent_path.read_text())
    assert sha(parent['executablePath']) == parent['executableSha256']
    for path, digest in {**parent['dependencies'], **parent['retainedLinkInputs']}.items():
        assert sha(path) == digest, path
    recipe = json.loads(args.main_build.read_text())
    assert sha(recipe['sourcePath']) == recipe['sourceSha256']
    assert sha(recipe['objectPath']) == recipe['objectSha256']
    assert recipe['objectPath'] in parent['linkCommand']
    component = json.loads(args.component.read_text())
    assert component['result'] == 'DEBUG_FONT_REAL_GL_COMPONENT_PASS'
    for path, digest in component['dependencies'].items():
        assert sha(path) == digest, path
    cache = Path(tempfile.mkdtemp(prefix='openshsm-debug-font-build-', dir='/private/tmp'))
    source, obj = cache / 'main.cpp', cache / 'main.cpp.o'
    shutil.copy2(recipe['sourcePath'], source)
    for name in ('BuildVersion.h', 'stock_first_image.h'):
        shutil.copy2(Path(recipe['sourcePath']).parent / name, cache / name)
    for name in ('stock_debug_overlay.h', 'stock_debug_font.h'):
        shutil.copy2(public / name, cache / name)
    command = list(recipe['compileCommand'])
    command[command.index(recipe['sourcePath'])] = str(source)
    command[command.index('-o') + 1] = str(obj)
    execute(command, root / 'export/build', cache / 'compile.log')
    for name in ('stock_debug_overlay.h', 'stock_debug_font.h'):
        assert str(cache / name) in (cache / 'compile.log').read_text()
    link = list(parent['linkCommand'])
    link[link.index(recipe['objectPath'])] = str(obj)
    exe = cache / 'OpenSHSM-0.0.42'
    link[link.index('-o') + 1] = str(exe)
    execute(link, root / 'export/build', cache / 'link.log')
    report = {'result': 'DEBUG_FONT_CURRENT_MAIN_COMPILED_NOT_LIVE_VERIFIED',
        'parentBuildPath': str(parent_path), 'parentBuildSha256': sha(parent_path),
        'mainBuildPath': str(args.main_build.resolve()), 'mainBuildSha256': sha(args.main_build),
        'componentPath': str(args.component.resolve()), 'componentSha256': sha(args.component),
        'sourcePath': str(source), 'sourceSha256': sha(source), 'objectPath': str(obj), 'objectSha256': sha(obj),
        'executablePath': str(exe), 'executableSha256': sha(exe),
        'archivePath': parent['archivePath'], 'archiveSha256': parent['archiveSha256'],
        'compileCommand': command, 'linkCommand': link,
        'retainedLinkInputs': {path: sha(path) for path in parent['linkCommand']
            if Path(path).is_file() and Path(path).suffix in ('.o', '.a') and path != recipe['objectPath']},
        'dependencies': {str(path): sha(path) for path in [Path(__file__), public / 'stock_debug_font_build.py',
            public / 'stock_debug_overlay.h', public / 'stock_debug_font.h',
            public / 'assets/debug-font/atlas.json', public / 'assets/debug-font/OFL.txt']},
        'limits': ['PC adaptation: antialiased JetBrains Mono Bold18px in existing overlay only.',
            'Main source unchanged; all guest objects/current runtime archive/CPU/aspect/audio retained.',
            'Component real GL verified; live game overlay requires inspection, not inferred from linking.']}
    path = cache / 'build.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    validate(path, parent_path, parent)
    print(report['result'], path, flush=True)


if __name__ == '__main__':
    main()

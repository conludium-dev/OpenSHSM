"""Gate the main-only font derivative against the already validated runtime parent."""
from pathlib import Path
import hashlib
import json


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate(path, parent_path, parent):
    build = json.loads(path.read_text())
    assert build['result'] == 'DEBUG_FONT_CURRENT_MAIN_COMPILED_NOT_LIVE_VERIFIED'
    assert Path(build['parentBuildPath']) == parent_path and build['parentBuildSha256'] == sha(parent_path)
    for file, digest in {**build['dependencies'], **build['retainedLinkInputs']}.items():
        assert sha(file) == digest, file
    main_path = Path(build['mainBuildPath'])
    assert sha(main_path) == build['mainBuildSha256']
    recipe = json.loads(main_path.read_text())
    source, obj = Path(build['sourcePath']), Path(build['objectPath'])
    assert source.parent == path.parent and obj.parent == path.parent
    assert sha(source) == build['sourceSha256'] == recipe['sourceSha256']
    assert sha(recipe['sourcePath']) == recipe['sourceSha256']
    assert sha(recipe['objectPath']) == recipe['objectSha256']
    assert sha(obj) == build['objectSha256']
    public = Path(__file__).resolve().parent
    for name in ('stock_debug_overlay.h', 'stock_debug_font.h'):
        assert sha(path.parent / name) == sha(public / name)
        assert str(path.parent / name) in (path.parent / 'compile.log').read_text()
    for name in ('BuildVersion.h', 'stock_first_image.h'):
        assert sha(path.parent / name) == sha(Path(recipe['sourcePath']).parent / name) == sha(public / name)
    command = list(recipe['compileCommand'])
    command[command.index(recipe['sourcePath'])] = str(source)
    command[command.index('-o') + 1] = str(obj)
    assert build['compileCommand'] == command
    component_path = Path(build['componentPath'])
    assert sha(component_path) == build['componentSha256']
    component = json.loads(component_path.read_text())
    assert component['result'] == 'DEBUG_FONT_REAL_GL_COMPONENT_PASS'
    for file, digest in component['dependencies'].items():
        assert sha(file) == digest, file
    exe = Path(build['executablePath'])
    assert exe.parent == path.parent and exe.name == 'OpenSHSM-0.0.42'
    expected = list(parent['linkCommand'])
    expected[expected.index(recipe['objectPath'])] = str(obj)
    expected[expected.index('-o') + 1] = str(exe)
    assert build['linkCommand'] == expected and sha(exe) == build['executableSha256']
    retained = {file: sha(file) for file in parent['linkCommand']
        if Path(file).is_file() and Path(file).suffix in ('.o', '.a') and file != recipe['objectPath']}
    assert build['retainedLinkInputs'] == retained
    assert build['archivePath'] == parent['archivePath']
    assert build['archiveSha256'] == parent['archiveSha256'] == sha(build['archivePath'])
    return exe

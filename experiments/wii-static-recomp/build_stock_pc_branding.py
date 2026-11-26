"""Main-only PC branding derivative of the verified BP-order candidate."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from stock_first_image_patch import adapt as adapt_first_image

parser = argparse.ArgumentParser()
parser.add_argument('--startup-capture', action='store_true')
parser.add_argument('--first-image', action='store_true')
args = parser.parse_args()
project = Path(__file__).resolve().parents[2]
public = Path(__file__).resolve().parent
root = project / 'work/private-game/static-recomp/stock-baseline'
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
parent_path = root / 'window-bp-order/build.json'
parent = json.loads(parent_path.read_text())
component_path = parent_path.parent / 'component-verification.json'
component = json.loads(component_path.read_text())
assert component['buildSha256'] == sha(parent_path)
assert component['result'] == 'BP_ORDER_NATIVE_SHADER_GPU_PIPELINE_RETAINED_PARENT_VERIFIED'
assert sha(parent['executablePath']) == parent['executableSha256']
assert sha(parent['archivePath']) == parent['archiveSha256']
assert all(sha(path) == digest for path, digest in parent['retainedInputs'].items())
main_recipe_path = root / 'window-post-present/build.json'
if not main_recipe_path.exists():
    main_recipe_path = Path('/private/tmp/openshsm-post-present-q98_ync5/build.json')
recipe = json.loads(main_recipe_path.read_text())['changes']['main.cpp']
original = Path(recipe['sourcePath'])
original_object = Path(recipe['objectPath'])
assert sha(original) == recipe['sourceSha256']
assert sha(original_object) == recipe['objectSha256']
assert str(original_object) in parent['linkCommand']
before = 'SDL_CreateWindow("NWiiRecomp",'
after = 'SDL_CreateWindow(OPENSHSM_RECOMP_WINDOW_TITLE,'
text = original.read_text()
assert text.count(before) == 1
patched = '#include "BuildVersion.h"\n' + text.replace(before, after, 1)
assert patched.removeprefix('#include "BuildVersion.h"\n').replace(after, before, 1) == text
capture_before = 'if ((++shot_frame % 300) == 0) {'
capture_after = 'if (++shot_frame <= 15 || (shot_frame <= 1200 && (shot_frame % 15) == 0)) {'
if args.startup_capture:
    assert patched.count(capture_before) == 1
    patched = patched.replace(capture_before, capture_after, 1)
    assert patched.replace(capture_after, capture_before, 1).removeprefix('#include "BuildVersion.h"\n').replace(after, before, 1) == text
cache = Path(tempfile.mkdtemp(prefix='openshsm-pc-branding-', dir='/private/tmp'))
if args.first_image:
    patched = adapt_first_image(patched)
    shutil.copyfile(public / 'stock_first_image.h', cache / 'stock_first_image.h')
source, obj = cache / 'main.cpp', cache / 'main.cpp.o'
source.write_text(patched)
shutil.copyfile(public / 'BuildVersion.h', cache / 'BuildVersion.h')
shutil.copyfile(original.parent / 'stock_debug_overlay.h', cache / 'stock_debug_overlay.h')
command = list(recipe['compileCommand'])
command[command.index(str(original))] = str(source)
command[command.index('-o') + 1] = str(obj)
compiled = subprocess.run(command, capture_output=True, text=True, timeout=180)
(cache / 'compile.log').write_text(compiled.stdout + compiled.stderr)
assert compiled.returncode == 0, compiled.stderr[-3000:]
assert str(cache / 'BuildVersion.h') in compiled.stderr
link = list(parent['linkCommand'])
link[link.index(str(original_object))] = str(obj)
exe = cache / 'OpenSHSM-0.0.42'
link[link.index('-o') + 1] = str(exe)
linked = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
(cache / 'link.log').write_text(linked.stdout + linked.stderr)
assert linked.returncode == 0, linked.stderr[-3000:]
assert b'OpenSHSM BUILD 0.0.42\0' in exe.read_bytes()
old_inputs = [value for value in parent['linkCommand'] if value.endswith(('.o', '.a'))]
new_inputs = [value for value in link if value.endswith(('.o', '.a'))]
assert len(old_inputs) == len(new_inputs)
assert [(old, new) for old, new in zip(old_inputs, new_inputs) if old != new] == [(str(original_object), str(obj))]
report = {
    'result': 'PC_BRANDING_MAIN_ONLY_COMPILED_LINKED_NOT_LIVE_VERIFIED',
    'version': '0.0.42', 'windowTitle': 'OpenSHSM BUILD 0.0.42',
    'startupCapture': args.startup_capture,
    'firstImage': args.first_image,
    'executablePath': str(exe), 'executableSha256': sha(exe),
    'parentBuildPath': str(parent_path), 'parentBuildSha256': sha(parent_path),
    'sourcePath': str(source), 'sourceSha256': sha(source),
    'originalSourcePath': str(original), 'originalSourceSha256': sha(original),
    'objectPath': str(obj), 'objectSha256': sha(obj),
    'compileCommand': command, 'linkCommand': link,
    'retainedLinkInputs': {str(Path(path) if Path(path).is_absolute() else root / 'export/build' / path): sha(Path(path) if Path(path).is_absolute() else root / 'export/build' / path) for path in old_inputs if path != str(original_object)},
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), public / 'BuildVersion.h', parent_path, component_path, main_recipe_path, original.parent / 'stock_debug_overlay.h']},
    'limits': ['PC branding only, not original Wii behavior.',
        'Main delta: one version include/title argument; optional bounded startup cadence in existing screenshot block.',
        'No guest, archive, input, audio, timing, assets or save changes.',
        'Native compilation and linking checked; live title and crash reproduction pending.',
        'Not registered with the strict diagnostic runner or published.']
}
path = cache / 'build.json'
if args.first_image:
    for dependency in [public / 'stock_first_image.h', public / 'stock_first_image_patch.py']:
        report['dependencies'][str(dependency)] = sha(dependency)
    report['limits'].append('First-image PC visibility gate only; uniform initial frames hidden, later uniform frames retained. Live window acceptance pending.')
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path, flush=True)

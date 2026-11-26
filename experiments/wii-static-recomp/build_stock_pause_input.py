"""Build a private Wii-1 pause-input derivative of the verified GX candidate."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile

from stock_debug_font_build import sha
from stock_pause_input_patch import keyboard, gamepad, manager, manager_header


def run(command, cwd, log):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=180)
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 0, (command, result.stderr[-4000:])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--renderer-build', type=Path, required=True)
    parser.add_argument('--renderer-gl-proof', type=Path, required=True)
    args = parser.parse_args()
    from stock_gx_renderer_texgen_validation import validate
    renderer_path = args.renderer_build.resolve()
    proof_path = args.renderer_gl_proof.resolve()
    renderer = json.loads(renderer_path.read_text())
    parent_path = Path(renderer['parentPath'])
    validate(renderer_path, parent_path, proof_path)

    public = Path(__file__).resolve().parent
    root = public.parents[1] / 'work/private-game/static-recomp/stock-baseline'
    recipe_path = root / 'window-quantization/build.json'
    recipe = json.loads(recipe_path.read_text())
    snapshot_recipe_path = root / 'input-snapshot-research/build.json'
    snapshot_recipe = json.loads(snapshot_recipe_path.read_text())
    archive_path = Path(renderer['archivePath'])
    members = {}
    for member in subprocess.check_output(['/usr/bin/ar', '-t', str(archive_path)], text=True).splitlines():
        if member.startswith('__'):
            continue
        body = subprocess.check_output(['/usr/bin/ar', '-p', str(archive_path), member])
        members[member] = hashlib.sha256(body).hexdigest()
    assert members == {**renderer['retainedMembers'],
        **{name: item['objectSha256'] for name, item in renderer['replacements'].items()}}

    cache = Path(tempfile.mkdtemp(prefix='openshsm-pause-input-', dir='/private/tmp'))
    header_original = root / 'input-snapshot-research/include/input/input_manager.h'
    assert sha(header_original) == snapshot_recipe['headerSha256']
    header = cache / 'input/input_manager.h'
    header.parent.mkdir(parents=True)
    header.write_text(manager_header(header_original.read_text()))
    replacements = {}
    inputs = {}
    for member, adapt in {'mouse_keyboard_source.cpp.o': keyboard,
            'gamepad_source.cpp.o': gamepad}.items():
        row = next(item for item in recipe['compiled'] if item.get('object') == member)
        inputs[member] = (root / 'window-quantization' / row['source'],
            row['sourceSha256'], row['objectSha256'], row['arguments'], adapt)
    inputs['input_manager.cpp.o'] = (root / 'input-snapshot-research/input_manager.cpp',
        snapshot_recipe['sourceSha256'], snapshot_recipe['objectSha256'],
        snapshot_recipe['arguments'], manager)
    for member, (original, source_hash, object_hash, arguments, adapt) in inputs.items():
        assert sha(original) == source_hash
        assert members[member] == object_hash
        source = cache / original.name
        obj = cache / member
        source.write_text(adapt(original.read_text()))
        command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-I', str(cache), *arguments,
            '-c', str(source), '-o', str(obj)]
        run(command, root / 'export/build', cache / (member + '.compile.log'))
        replacements[member] = {'originalPath': str(original),
            'originalSha256': source_hash, 'sourcePath': str(source),
            'sourceSha256': sha(source), 'objectPath': str(obj),
            'objectSha256': sha(obj), 'compileCommand': command}

    archive = cache / 'libnwiiruntime.a'
    shutil.copy2(archive_path, archive)
    for member, row in replacements.items():
        run(['/usr/bin/ar', 'r', str(archive), row['objectPath']],
            root / 'export/build', cache / (member + '.ar.log'))
    run(['/usr/bin/ranlib', str(archive)], root / 'export/build', cache / 'ranlib.log')
    for member, digest in members.items():
        body = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
        assert hashlib.sha256(body).hexdigest() == (
            replacements[member]['objectSha256'] if member in replacements else digest), member

    link = list(renderer['linkCommand'])
    link[link.index(str(archive_path))] = str(archive)
    exe = cache / 'OpenSHSMStockPauseInput'
    link[link.index('-o') + 1] = str(exe)
    run(link, root / 'export/build', cache / 'link.log')
    report = {'result': 'PAUSE_INPUT_PRIVATE_BUILT_NOT_GAME_VERIFIED',
        'rendererBuildPath': str(renderer_path), 'rendererBuildSha256': sha(renderer_path),
        'rendererGlProofPath': str(proof_path), 'rendererGlProofSha256': sha(proof_path),
        'archivePath': str(archive), 'archiveSha256': sha(archive),
        'executablePath': str(exe), 'executableSha256': sha(exe),
        'headerPath': str(header), 'headerSha256': sha(header),
        'replacements': replacements,
        'retainedMembers': {name: digest for name, digest in members.items() if name not in replacements},
        'linkCommand': link,
        'dependencies': {str(path.resolve()): sha(path) for path in
            [Path(__file__), public / 'stock_pause_input_patch.py', recipe_path,
             snapshot_recipe_path, header_original,
             renderer_path, proof_path, *[Path(row['originalPath']) for row in replacements.values()]]},
        'limits': ['Private PC input adaptation; Wii 1 is mapped to Enter/Escape and controller Start.',
            'Wii Plus moves to F and controller right shoulder; PAD Start remains unchanged.',
            'On bounded snapshot overflow, a queued Wii 1 press is carried into the next queued sample; repeated unread presses may coalesce.',
            'No live pause, skip-button, keyboard event or controller acceptance from this build alone.']}
    path = cache / 'build.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, flush=True)


if __name__ == '__main__':
    main()

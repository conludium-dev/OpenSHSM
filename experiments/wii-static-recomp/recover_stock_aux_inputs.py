"""Recover remaining current link inputs through the retained build transformations."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
from stock_first_image_patch import adapt as first_image
from stock_hidden_gl_patch import adapt as hidden_gl


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def patched(text, patches):
    for before, after in patches:
        assert text.count(before) == 1, before[:100]
        text = text.replace(before, after, 1)
    return text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--current', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    public = Path(__file__).resolve().parent
    root = public.parents[1] / 'work/private-game/static-recomp/stock-baseline'
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    current = json.loads(args.current.read_text())
    old = lambda name: next(v for v in current['linkCommand'] if Path(v).name == name)
    load = lambda name: json.loads((root / name / 'build.json').read_text())
    inputs = []
    def compile_source(name, text, command, expected=None):
        source, obj = output / name, output / (name + '.o')
        source.write_text(text)
        if expected:
            assert sha(source) == expected, name
        command = list(command)
        command[command.index('-c') + 1] = str(source)
        command[command.index('-o') + 1] = str(obj)
        command[1:1] = ['-I', str(output)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
        (output / (name + '.compile.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-4000:]
        inputs.append({'sourcePath': str(source), 'sourceSha256': sha(source),
            'objectPath': str(obj), 'objectSha256': sha(obj), 'compileCommand': command,
            'replaces': old(obj.name)})
        print('RECOVERED', obj.name, flush=True)

    numeric = args.reference.parent / 'dolphin/Source/Core/Common/FloatUtils.cpp'
    reference = json.loads(args.reference.read_text())
    assert sha(numeric) == next(r['sha256'] for r in reference['references'] if r['path'] == str(numeric))
    cxx = '/Library/Developer/CommandLineTools/usr/bin/c++'
    sdk = '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk'
    compile_source('FloatUtils.cpp', numeric.read_text(), [cxx, '-std=c++20', '-O2',
        '-frounding-math', '-fno-fast-math', '-isysroot', sdk,
        '-I', str(args.reference.parent / 'shim'), '-I', str(args.reference.parent / 'dolphin/Source/Core'),
        '-c', 'source', '-o', 'object'])

    record = load('window-dispatch-select')
    source = Path(record['originalSourcePath'])
    assert sha(source) == record['dependencies'][str(source)]
    text = patched(source.read_text(), [record['abiRename']])
    compile_source('dispatch.cpp', text, record['compileCommand'], record['sourceSha256'])
    record = load('window-dispatch-o2')
    source = Path(record['masterOriginalPath'])
    assert sha(source) == record['masterOriginalSha256']
    text = record['includeAddition'] + patched(source.read_text(), record['masterPatches'])
    compile_source('fixed.cpp', text, record['compileCommands'][0], record['masterSourceSha256'])

    movie = load('window-movie-late')
    header = Path(movie['headerOriginalPath'])
    (output / header.name).write_text(patched(header.read_text(), movie['headerPatches']))
    for number, record in movie['changes'].items():
        original = Path(record['originalPath'])
        assert sha(original) == record['originalSha256']
        compile_source(original.name, original.read_text(), [cxx, *record['arguments'],
            '-I', str(original.parent), '-I', str(root / 'headless-psq-scale'),
            '-I', str(root / 'window-movie-dma'),
            '-c', 'source', '-o', 'object'], record['sourceSha256'])

    source = root / 'headless-sc-pc/output_38.cpp'
    record = load('headless-sc-pc')
    assert sha(source) == record['sourceSha256']
    calls = [(4, '80212FA0'), (5, '80212FC4'), (6, '80212FC4'), (7, '80212FC8')]
    text = patched(source.read_text(), [(f'    stock_loading_observation::observe_context(ctx, {stage}, 0x{pc});\n', '')
        for stage, pc in calls])
    flags = json.loads((root / 'window-fp-guard/output_38.cpp.record.json').read_text())['arguments']
    compile_source(source.name, text, [cxx, *flags, '-c', 'source', '-o', 'object'])

    completed = load('window-completed-frame')['changes']['main.cpp']
    original = Path(completed['originalPath'])
    assert sha(original) == completed['originalSha256']
    text = patched(original.read_text(), completed['patches'])
    assert hashlib.sha256(text.encode()).hexdigest() == completed['sourceSha256']
    post = load('window-post-present')['changes']['main.cpp']
    assert completed['sourceSha256'] == post['originalSha256']
    text = patched(text, post['patches'])
    assert hashlib.sha256(text.encode()).hexdigest() == post['sourceSha256']
    text = '#include "BuildVersion.h"\n' + patched(text,
        [('SDL_CreateWindow("NWiiRecomp",', 'SDL_CreateWindow(OPENSHSM_RECOMP_WINDOW_TITLE,')])
    text = hidden_gl(first_image(text))
    for name in ('BuildVersion.h', 'stock_debug_overlay.h', 'stock_debug_font.h', 'stock_first_image.h'):
        shutil.copy2(public / name, output / name)
    compile_source('main.cpp', text, post['compileCommand'])
    report = {'result': 'REGENERATED_AUXILIARY_INPUTS_NOT_LINKED', 'inputs': inputs,
        'dependencies': {str(p.resolve()): sha(p) for p in [Path(__file__), args.current, args.reference,
            public / 'stock_first_image_patch.py', public / 'stock_hidden_gl_patch.py',
            public / 'stock_debug_overlay.h', public / 'stock_debug_font.h']},
        'limits': ['Historical source hashes checked where retained; temporary object identity is not asserted.',
            'Main recovered through completed-frame/post-present/branding/first-image/font/hidden-GL chain.',
            'Full linked runtime, visual/audio equivalence and depth candidate remain unverified.']}
    (output / 'recovery.json').write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], len(inputs), flush=True)


if __name__ == '__main__':
    main()

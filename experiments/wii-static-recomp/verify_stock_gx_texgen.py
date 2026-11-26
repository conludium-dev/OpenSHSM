"""Compare texture arithmetic against unchanged pinned software-transform routines."""
from pathlib import Path
import argparse
import json
import re
import shutil
import subprocess
import tempfile
from stock_debug_font_build import sha
from build_stock_sysconf import execute


def extract(text, name):
    match = re.search(r'(?m)^(?:static )?(?:inline )?void ' + name + r'\(', text)
    assert match, name
    opening = text.index('{', match.start())
    depth = 1
    end = opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[match.start():end]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', type=Path, required=True)
    args = parser.parse_args()
    reference = json.loads(args.reference.read_text())
    assert reference['result'] == 'PINNED_GX_TEXGEN_REFERENCE_READY_NOT_RUNTIME_CODE'
    assert reference['revision'] == 'e2ad09306e6d371f7272205bdc363da9fe05fe08'
    files = {Path(row['path']).name: Path(row['path']) for row in reference['references']}
    for row in reference['references']:
        assert sha(row['path']) == row['sha256']
    text = files['TransformUnit.cpp'].read_text()
    names = ('MultiplyVec2Mat24', 'MultiplyVec2Mat34', 'MultiplyVec3Mat24',
        'MultiplyVec3Mat34', 'TransformTexCoordRegular', 'TransformTexCoord')
    bodies = {name: extract(text, name) for name in names}
    public = Path(__file__).resolve().parent
    cache = Path(tempfile.mkdtemp(prefix='openshsm-gx-texgen-reference-', dir='/private/tmp'))
    shutil.copy2(files['Matrix.h'], cache / 'Matrix.h')
    source = cache / 'reference.cpp'
    source.write_text('#include "stock_gx_texgen.h"\n#include <bit>\n'
        '#include "stock_gx_texgen_reference_fixture.h"\n'
        '#define ASSERT(x) assert(x)\n#define ERROR_LOG_FMT(...) throw std::runtime_error("reference invalid texgen")\n'
        'namespace pinned {\n' + '\n\n'.join(bodies.values()) + '\n}\n')
    executable = cache / 'probe'
    command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-isysroot',
        '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk', '-std=c++20', '-O1',
        '-ffp-contract=off', '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
        '-DOPENSHSM_PINNED_TEXGEN', '-I', str(cache), '-I', str(public),
        str(public / 'stock_gx_texgen_probe.cpp'), str(source), '-o', str(executable)]
    execute(command, public, cache / 'compile.log')
    result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=20)
    (cache / 'run.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and 'GX_TEXGEN_PINNED_DIFFERENTIAL_PASS 96' in result.stdout, (result.returncode, result.stderr)
    report = {'result': 'GX_TEXGEN_PINNED_ARITHMETIC_PASS_NOT_RUNTIME_RENDER',
        'referenceRevision': reference['revision'], 'referencePath': str(args.reference.resolve()),
        'functions': list(bodies), 'output': result.stdout.strip(), 'compileCommand': command,
        'executableSha256': sha(executable), 'sourcePath': str(source), 'sourceSha256': sha(source),
        'dependencies': {str(path.resolve()): sha(path) for path in [Path(__file__), args.reference,
            *files.values(), *[public / name for name in ('stock_gx_texgen.h',
                'stock_gx_texgen_probe.cpp', 'stock_gx_texgen_reference_fixture.h')]]},
        'limits': ['Unchanged pinned transform bodies and actual Common::Vec3 math; explicit bounded state/bitfield/input fixture.',
            '96 source/form/projection/dual jobs,4096 mixed nonidentity banks/post-normalization/indices/scales/emboss jobs, basic color/qzero/NaN cases.',
            'Bounds/invalid-source/forward-emboss refusals are PC adaptations, not compared with reference undefined/error paths.',
            'Colors are caller-supplied post-lighting values; coordinates remain S/T/Q with BP scaling, not normalized GL sampler coordinates.',
            'Not original Wii hardware, actual SHSM texgen commands/scene, complete matrix snapshot/renderer/shader/pixel integration or FPS acceptance.',
            'Game remains closed; no existing executable/assets/release/publication changes.']}
    path = cache / 'verification.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, flush=True)


if __name__ == '__main__':
    main()

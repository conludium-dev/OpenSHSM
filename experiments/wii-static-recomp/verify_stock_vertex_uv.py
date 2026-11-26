"""Compare retained and patched actual FIFO decoding; no game or renderer launch."""
from pathlib import Path
import argparse
import json
import hashlib
import re
import subprocess
import tempfile
from build_stock_sysconf import execute
from stock_debug_font_build import sha
from stock_vertex_uv_patch import adapt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ax-build', type=Path, required=True)
    parser.add_argument('--sources', action='store_true')
    parser.add_argument('--normal-reference', type=Path)
    args = parser.parse_args()
    public = Path(__file__).resolve().parent
    root = public.parents[1] / 'work/private-game/static-recomp/stock-baseline'
    build = json.loads(args.ax_build.read_text())
    assert sha(build['archivePath']) == build['archiveSha256']
    recipe_path = root / 'window-bp-order/build.json'
    recipe = json.loads(recipe_path.read_text())
    source_path = Path(recipe['sourcePath'])
    assert sha(source_path) == recipe['sourceSha256']
    assert build['retainedRuntimeMembers']['fifo_parser.cpp.o'] == recipe['objectSha256']
    member = subprocess.check_output(['/usr/bin/ar', '-p', build['archivePath'], 'fifo_parser.cpp.o'])
    assert hashlib.sha256(member).hexdigest() == recipe['objectSha256']
    cache = Path(tempfile.mkdtemp(prefix='openshsm-vertex-uv-', dir='/private/tmp'))
    source = cache / 'fifo_parser.cpp'
    patch = adapt
    extra_dependencies = []
    extra_arguments = []
    reference_object = None
    if args.sources:
        from stock_vertex_sources_patch import adapt as adapt_sources, adapt_header
        patch = adapt_sources
        header = root / 'export/nWiiRuntime/include/runtime/gx/fifo_parser.h'
        adapted_header = cache / 'runtime/gx/fifo_parser.h'
        adapted_header.parent.mkdir(parents=True)
        adapted_header.write_text(adapt_header(header.read_text()))
        extra_dependencies = [header, adapted_header, public / 'stock_vertex_sources_patch.py',
            public / 'stock_gx_vertex_sources.h', public / 'stock_gx_attribute_bounds.h',
            public / 'stock_gx_texgen.h', public / 'stock_gx_texgen_bridge.h']
        extra_arguments = ['-DOPENSHSM_SOURCE_VERTEX', '-I', str(cache)]
        assert args.normal_reference, '--sources requires pinned normal-loader reference.'
        reference = json.loads(args.normal_reference.read_text())
        assert reference['result'] == 'PINNED_GX_TEXGEN_REFERENCE_READY_NOT_RUNTIME_CODE'
        assert reference['revision'] == 'e2ad09306e6d371f7272205bdc363da9fe05fe08'
        row = next(row for row in reference['references'] if Path(row['path']).name == 'VertexLoader_Normal.cpp')
        normal = Path(row['path'])
        assert sha(normal) == row['sha256']
        original = normal.read_text()
        begin = original.index('template <typename T>\nconstexpr float FracAdjust')
        end = original.index('using Common::EnumMap;', begin)
        reference_source = cache / 'normal-reference.cpp'
        reference_source.write_text('#include "stock_gx_normal_reference_fixture.h"\n#define LOG_NORM()\n'
            'namespace pinned_normal {\n' + original[begin:end] + '\n'
            '#include "stock_gx_normal_reference_dispatch.h"\n}\n')
        reference_object = cache / 'normal-reference.o'
        reference_command = list(recipe['compileCommand'])
        reference_command[1:1] = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-I', str(cache)]
        reference_command[reference_command.index(str(source_path))] = str(reference_source)
        reference_command[reference_command.index('-o') + 1] = str(reference_object)
        execute(reference_command, root / 'export/build', cache / 'normal-reference-compile.log')
        extra_arguments.append('-DOPENSHSM_PINNED_NORMAL')
        extra_dependencies += [args.normal_reference, normal, reference_source,
            public / 'stock_gx_normal_reference_fixture.h', public / 'stock_gx_normal_reference_dispatch.h']
    source.write_text(patch(source_path.read_text()))
    compiler = list(recipe['compileCommand'])
    instrumentation = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
    compiler[1:1] = instrumentation
    compiler[1:1] = extra_arguments
    compiler.insert(1, '-H')
    probe = public / 'stock_vertex_uv_probe.cpp'
    probe_obj = cache / 'probe.o'
    compiler[compiler.index(str(source_path))] = str(probe)
    compiler[compiler.index('-o') + 1] = str(probe_obj)
    execute(compiler, root / 'export/build', cache / 'probe-compile.log')
    link = list(build['linkCommand'])
    link[1:1] = instrumentation
    main_obj = next(path for path in link if Path(path).name == 'main.cpp.o')
    link[link.index(main_obj)] = str(root / 'window-quantization/contract-entry.cpp.o')
    link.insert(1, str(probe_obj))
    if reference_object:
        link.insert(2, str(reference_object))
    baseline = cache / 'baseline'
    link[link.index('-o') + 1] = str(baseline)
    execute(link, root / 'export/build', cache / 'baseline-link.log')
    command = list(recipe['compileCommand'])
    command[1:1] = instrumentation
    command[1:1] = extra_arguments
    command.insert(1, '-H')
    command[command.index(str(source_path))] = str(source)
    obj = cache / 'fifo_parser.cpp.o'
    command[command.index('-o') + 1] = str(obj)
    execute(command, root / 'export/build', cache / 'candidate-compile.log')
    candidate = cache / 'candidate'
    link.insert(2, str(obj))
    link[link.index('-o') + 1] = str(candidate)
    execute(link, root / 'export/build', cache / 'candidate-link.log')
    outputs = {}
    for label, argv, expected in [('baseline', [str(baseline), 'baseline'], 'UV_BASELINE_LOSS_REPRODUCED 510'),
            ('candidate', [str(candidate)], 'UV_EIGHT_DIRECT_ATTRIBUTES_PASS 510')]:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=20)
        (cache / (label + '-run.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0 and expected in result.stdout, (label, result.returncode, result.stderr)
        if args.sources and label == 'candidate':
            assert 'RAW_VERTEX_SOURCES_UV_PASS' in result.stdout
            assert 'PINNED_NORMAL_LOADER_64_PASS' in result.stdout
            assert '720direct/indexed/fixed-UV jobs' in result.stdout
            assert 'GX_DECODE_TO_TEXGEN_BRIDGE_PASS 8source-rows/510draw+720numeric-fixtures' in result.stdout
        outputs[label] = result.stdout.strip()
    report = {'result': 'ACTUAL_FIFO_VERTEX_SOURCES_UV_PASS_NOT_GAME_RENDER' if args.sources else 'ACTUAL_FIFO_DIRECT_UV_LOSS_AND_CORRECTION_PASS_NOT_GAME_RENDER',
        'outputs': outputs, 'compileCommand': command, 'candidateLinkCommand': link,
        'sourcePath': str(source), 'sourceSha256': sha(source),
        'executables': {str(path): sha(path) for path in (baseline, candidate)},
        'dependencies': {str(path.resolve()): sha(path) for path in [Path(__file__), probe,
            public / 'stock_vertex_uv_patch.py', args.ax_build, recipe_path, source_path, *extra_dependencies]},
        'limits': ['Actual current archive decoder reproduces seven UV stream losses; candidate linked decoder corrects direct F32 attributes.',
            'Probe and candidate FIFO instrumented ASan/UBSan; retained archive is not fully instrumented.',
            '510 masks/component variants with two vertices plus truncation; 720 indexed/fixed-point UV fixtures in source mode.',
            'Renderer still consumes only UV0 and shader aliases UV0 for all texgens: full texgen/matrix/shader integration pending.',
            'Synthetic data, not original Wii behavior/full SHSM scene/pixels/performance; no game build/window or asset changes.']}
    if args.sources:
        report['limits'].extend([
            'Sources appended to existing DrawRaw; VertexData/GXCommand ABI unchanged, DrawRaw tail extended. All relevant consumers still require integration validation.',
            'Shared raw/cache ownership copied before attaching sources or clearing bytes; original cache remains unchanged.',
            '64 normal format/direct/index8/index16/NBT single/index3 jobs compared to unchanged pinned loader templates with endian/reader/state fixtures.',
            'Full-span MEM1/MEM2/locked-cache boundaries, index-address overflow and truncated indices refuse; these are PC guards, not hardware fault behavior.',
            '720 direct/index8/index16 UV jobs cover all eight channels, numeric formats, one/two components and shifts 0/3/31; three UV pointer/truncation guards. All 510 draw fixtures and 720 numeric fixtures feed decoded sources into XF/BP texgen bridge for all eight UV rows. Indexed color, missing cached attributes and real scene matrices/render handoff remain pending.',
            'No current archive/game candidate replaced; renderer does not consume DrawRaw.sources yet.'])
    includes = (cache / 'candidate-compile.log').read_text() + (cache / 'probe-compile.log').read_text()
    for name in re.findall(r'^\.+ (/[^\n]+)$', includes, re.MULTILINE):
        header = Path(name)
        if header.is_file() and header.is_relative_to(public.parents[1]):
            report['dependencies'][str(header)] = sha(header)
    for name in link:
        path = Path(name)
        if path.is_file() and path.suffix in ('.a', '.o'):
            report['dependencies'][str(path)] = sha(path)
    path = cache / 'verification.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, flush=True)


if __name__ == '__main__':
    main()

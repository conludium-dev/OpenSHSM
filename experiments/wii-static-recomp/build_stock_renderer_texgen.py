"""Build a private GX source/texgen renderer derivative of the current 0.0.42 archive."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from stock_debug_font_build import sha
from stock_vertex_sources_patch import adapt as adapt_parser, adapt_header
from stock_gx_renderer_texgen_patch import renderer as adapt_renderer, shader as adapt_shader, depth_state as adapt_depth_state
from stock_gx_direct_append_patch import adapt as adapt_gx
from stock_gx_display_list_memory_patch import parser as adapt_display_lists, snapshots as adapt_snapshots
from stock_gx_vertex_reuse_patch import adapt as adapt_vertex_reuse


def run(command, cwd, log):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=180)
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 0, (command, result.stderr[-4000:])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--fifo-proof', type=Path, required=True)
    parser.add_argument('--bridge-proof', type=Path, required=True)
    args = parser.parse_args()
    public = Path(__file__).resolve().parent
    root = public.parents[1] / 'work/private-game/static-recomp/stock-baseline'
    parent = json.loads(args.parent.read_text())
    fifo = json.loads(args.fifo_proof.read_text())
    bridge = json.loads(args.bridge_proof.read_text())
    assert parent['result'] == 'AXWII_DEVICE_CURRENT_DSP_COMPILED_NOT_LIVE_VERIFIED'
    assert fifo['result'] == 'ACTUAL_FIFO_VERTEX_SOURCES_UV_PASS_NOT_GAME_RENDER'
    assert bridge['result'] == 'GX_TEXGEN_STATE_BRIDGE_PASS_NOT_GAME_RENDER'
    for report in (fifo, bridge):
        for path, digest in report['dependencies'].items():
            assert sha(path) == digest, path
    assert sha(parent['archivePath']) == parent['archiveSha256']
    assert sha(parent['executablePath']) == parent['executableSha256']
    for path, digest in parent['retainedLinkInputs'].items():
        assert sha(path) == digest, path

    members = {}
    for member in subprocess.check_output(['/usr/bin/ar', '-t', parent['archivePath']], text=True).splitlines():
        if member.startswith('__'):
            continue
        body = subprocess.check_output(['/usr/bin/ar', '-p', parent['archivePath'], member])
        members[member] = hashlib.sha256(body).hexdigest()
    expected = dict(parent['retainedRuntimeMembers'])
    expected['hw_dsp.cpp.o'] = parent['objectSha256']
    assert members == expected

    fifo_recipe = json.loads((root / 'window-bp-order/build.json').read_text())
    gx_recipe = json.loads((root / 'window-pe-cadence/build.json').read_text())
    renderer_recipe = json.loads((root / 'window-pe-execute/build.json').read_text())['changes']['renderer_gl.cpp']
    shader_recipe = next(row for row in json.loads((root / 'headless-tev-banks/build.json').read_text())['compiled']
        if row['member'] == 'tev_shader_gen.cpp.o')
    assert sha(fifo_recipe['sourcePath']) == fifo_recipe['sourceSha256']
    assert sha(gx_recipe['sourcePath']) == gx_recipe['sourceSha256']
    assert sha(renderer_recipe['sourcePath']) == renderer_recipe['sourceSha256']
    shader_original = root / 'headless-tev-banks/tev_shader_gen.cpp'
    assert sha(shader_original) == shader_recipe['sourceSha256']
    assert members['fifo_parser.cpp.o'] == fifo_recipe['objectSha256']
    assert members['gx.cpp.o'] == gx_recipe['objectSha256']
    assert members['renderer_gl.cpp.o'] == renderer_recipe['objectSha256']
    assert members['tev_shader_gen.cpp.o'] == shader_recipe['objectSha256']

    scratch = public.parents[1] / '_scratch/tmp'
    scratch.mkdir(parents=True, exist_ok=True)
    cache = Path(tempfile.mkdtemp(prefix='openshsm-renderer-texgen-', dir=scratch))
    header_original = root / 'export/nWiiRuntime/include/runtime/gx/fifo_parser.h'
    header = cache / 'runtime/gx/fifo_parser.h'
    header.parent.mkdir(parents=True)
    header.write_text(adapt_header(header_original.read_text()))
    sources = {
        'gx.cpp.o': (Path(gx_recipe['sourcePath']), lambda text: adapt_snapshots(adapt_gx(text)), gx_recipe['compileCommand']),
        'fifo_parser.cpp.o': (Path(fifo_recipe['sourcePath']), lambda text: adapt_display_lists(adapt_parser(text)), fifo_recipe['compileCommand']),
        'renderer_gl.cpp.o': (Path(renderer_recipe['sourcePath']), lambda text: adapt_vertex_reuse(adapt_depth_state(adapt_renderer(text))), renderer_recipe['compileCommand']),
        'tev_shader_gen.cpp.o': (shader_original, adapt_shader,
            ['/Library/Developer/CommandLineTools/usr/bin/c++', *shader_recipe['arguments'],
             '-c', str(shader_original), '-o', str(root / 'headless-tev-banks/tev_shader_gen.cpp.o')]),
    }
    replacements = {}
    for member, (original, adapt, command) in sources.items():
        source = cache / original.name
        obj = cache / member
        source.write_text(adapt(original.read_text()))
        if member == 'fifo_parser.cpp.o':
            assert hashlib.sha256(adapt_parser(original.read_text()).encode()).hexdigest() == fifo['sourceSha256']
        command = list(command)
        command[1:1] = ['-I', str(cache)]
        command.append('-O2')
        command[command.index(str(original))] = str(source)
        command[command.index('-o') + 1] = str(obj)
        run(command, root / 'export/build', cache / (member + '.compile.log'))
        replacements[member] = {'sourcePath': str(source), 'sourceSha256': sha(source),
            'objectPath': str(obj), 'objectSha256': sha(obj), 'compileCommand': command}

    archive = cache / 'libnwiiruntime.a'
    shutil.copy2(parent['archivePath'], archive)
    for member in replacements:
        run(['/usr/bin/ar', 'r', str(archive), replacements[member]['objectPath']],
            root / 'export/build', cache / (member + '.ar.log'))
    run(['/usr/bin/ranlib', str(archive)], root / 'export/build', cache / 'ranlib.log')
    for member, digest in members.items():
        body = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
        actual = hashlib.sha256(body).hexdigest()
        assert actual == (replacements[member]['objectSha256'] if member in replacements else digest), member
    link = list(parent['linkCommand'])
    link[link.index(parent['archivePath'])] = str(archive)
    exe = cache / 'OpenSHSMStockRendererTexgen'
    link[link.index('-o') + 1] = str(exe)
    run(link, root / 'export/build', cache / 'link.log')
    report = {'result': 'CURRENT_RENDERER_TEXGEN_PRIVATE_BUILT_NOT_GAME_VERIFIED',
        'parentPath': str(args.parent.resolve()), 'parentSha256': sha(args.parent),
        'archivePath': str(archive), 'archiveSha256': sha(archive),
        'executablePath': str(exe), 'executableSha256': sha(exe),
        'replacements': replacements, 'retainedMembers': {k: v for k, v in members.items() if k not in replacements},
        'headerPath': str(header), 'headerSha256': sha(header),
        'linkCommand': link,
        'dependencies': {str(path.resolve()): sha(path) for path in [Path(__file__), args.parent,
            args.fifo_proof, args.bridge_proof, header_original,
            public / 'stock_vertex_sources_patch.py', public / 'stock_vertex_uv_patch.py',
            public / 'stock_gx_vertex_sources.h', public / 'stock_gx_attribute_bounds.h',
            public / 'stock_gx_texgen.h', public / 'stock_gx_texgen_bridge.h',
            public / 'stock_gx_shader_key.h',
            public / 'stock_gx_direct_append_patch.py',
            public / 'stock_gx_display_list_memory_patch.py', public / 'stock_gx_display_list_memory.h',
            public / 'stock_gx_vertex_reuse_patch.py',
            public / 'stock_gx_renderer_texgen_patch.py',
            root / 'window-bp-order/build.json', root / 'window-pe-execute/build.json',
            root / 'window-pe-cadence/build.json',
            root / 'headless-tev-banks/build.json', *[value[0] for value in sources.values()]]},
        'limits': ['Private derivative only; no launcher registration or runtime/pixel acceptance.',
            'Regular texgens use decoded raw sources and ordered XF/BP state; unsupported color/emboss/missing attributes fall back to prior UV0 behavior.',
            'Postmatrix is held in the existing renderer because GXState has no XF 0x500 bank; per-draw timing/ownership needs validation.',
            'CP packet commands append directly to the existing GX vector; ordering and PE events are unchanged.',
            'Display lists accept bounded Wii MEM1/MEM2 spans; snapshot keys preserve the physical memory bank.',
            'Replaced GX/FIFO/renderer/shader objects use -O2 without fast-math; original guest timing is unchanged.',
            'BP40 depth/projection candidate is isolated from the default renderer until game cutscene validation succeeds.',
            'RG8 EFB copies sample as IA8 (R,R,R,G); later copies reset the texture swizzle. Other copy-format conversions remain incomplete.',
            'TEV raster/texture swap selectors and tables are applied and included in shader-cache identity.',
            'TEV comparison modes use wrapped8-bit operands; regular blending remains floating point.',
            'No claim of correct game graphics, Q-zero sampling, performance, audio or original Wii behavior.']}
    path = cache / 'build.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, flush=True)


if __name__ == '__main__':
    main()

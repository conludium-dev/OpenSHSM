"""Reproduce current graphics runtime sources from a verified own-Wii export."""
from pathlib import Path
import argparse
import json
import shutil

from export_stock_wii_us_copy import digest
from recover_stock_late_adapter_guest import record
from stock_efb_retile_patch import adapt_renderer
from stock_tev_bank_patch import state as adapt_gx_state
from stock_vertex_sources_patch import adapt_header
import stock_gx_completion_batch_patch as completion_batch
import stock_efb_indexed_view_patch as indexed_view
import stock_gx_snapshot_timing_patch as snapshot_timing
import stock_gx_vertex_size_patch as vertex_size
import stock_gx_command_workspace_patch as command_workspace
import stock_gx_profile_window_patch as phase_profile
import stock_gx_vertex_hotpath_patch as vertex_hotpath
from stock_gx_renderer_texgen_patch import depth_persistence
from stock_efb_wii_address_patch import adapt as wii_address
from verify_wii_us_copy import audit_copy


MANIFEST = Path(__file__).with_name('stock-graphics-runtime-wii-us-r5wea4-rev0.json')
SOURCES = (
    'src/hle/gx.cpp',
    'src/hle/gx/fifo_parser.cpp',
    'src/hle/gx/renderer_gl.cpp',
    'src/hle/gx/tev_shader_gen.cpp',
    'src/hle/texture_cache_gl.cpp',
)
FIFO_HEADER = 'include/runtime/gx/fifo_parser.h'
GX_STATE_HEADER = 'include/runtime/gx_state.h'


def apply_edits(text, edits):
    lines = text.splitlines(keepends=True)
    for edit in reversed(edits):
        start = edit['startLine']
        before = edit['old'].splitlines(keepends=True)
        after = edit['new'].splitlines(keepends=True)
        if start < 0 or lines[start:start + len(before)] != before:
            raise ValueError('Graphics patch site differs')
        lines[start:start + len(before)] = after
    return ''.join(lines)


def apply_pairs(text, pairs):
    for before, after in pairs:
        if text.count(before) != 1:
            raise ValueError('Texture observer patch site differs')
        text = text.replace(before, after, 1)
    return text


def texture_header(public, recipe):
    text = apply_pairs((public / 'stock_texture_observation.h').read_text(), recipe['headerPatches'])
    marker = 'namespace openshsm::experiment {\n'
    if text.count(marker) != 1:
        raise ValueError('Texture observer namespace differs')
    text = text.replace(marker, marker + recipe['headerHelpers'], 1)
    gate = 'static stock_movie_capture_gate::Gate gate(std::getenv("NWII_TEXTURE_CAPTURE_AFTER_MS"));'
    if text.count(gate) != 2:
        raise ValueError('Texture observer gate differs')
    text = text.replace(gate, 'auto& gate = texture_observation_gate();')
    return apply_pairs(text, recipe['headerCoherencePatches'])


def recover(game_data, stock_export, destination):
    game = Path(audit_copy(game_data)['source']).resolve(strict=True)
    stock_export = Path(stock_export).expanduser().resolve(strict=True)
    destination = Path(destination).expanduser().absolute()
    if not destination.parent.is_dir():
        raise ValueError('Destination parent does not exist')
    destination = destination.parent.resolve(strict=True) / destination.name
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destination must be a fresh directory')
    if any(destination == source or source in destination.parents
            for source in (game, stock_export)):
        raise ValueError('Destination must be outside Wii DATA and stock export')
    if shutil.disk_usage(destination.parent).free < 16 * 1024 * 1024:
        raise ValueError('Insufficient free space')

    expected = json.loads(MANIFEST.read_text())
    stock_manifest = json.loads(Path(__file__).with_name(
        'stock-export-wii-us-r5wea4-rev0.json').read_text())
    stock_result = json.loads((stock_export.parent / 'export-result.json').read_text())
    dol_path = game / 'sys/main.dol'
    if expected['gameId'] != 'R5WEA4' or expected['revision'] != 0 or \
            expected['source'] != 'stock-export-wii-us-r5wea4-rev0.json' or \
            stock_result['result'] != 'OWNER_WII_US_R5WEA4_REV0_STOCK_SOURCE_EXPORTED_NOT_GAME_BUILD' or \
            stock_result['dolSha256'] != digest(dol_path) or \
            set(expected['edits']) != set(SOURCES):
        raise ValueError('Stock graphics do not match verified Wii US rev0 DATA')
    generated = {}
    for name in SOURCES:
        original = (stock_export / 'nWiiRuntime' / name).read_bytes()
        if record(original) != stock_manifest['runtime'][name]:
            raise ValueError(f'Stock graphics source changed: {name}')
        text = apply_edits(original.decode(), expected['edits'][name])
        if name == 'src/hle/texture_cache_gl.cpp':
            if record(text.encode()) != expected['textureEvictionStage']:
                raise RuntimeError('Texture eviction stage differs')
            before, after = expected['textureLatePatch']
            if text.count(before) != 1:
                raise ValueError('Texture late patch site differs')
            text = text.replace(before, after, 1)
        generated[name] = text.encode()
    original_header = (stock_export / 'nWiiRuntime' / FIFO_HEADER).read_bytes()
    if record(original_header) != stock_manifest['runtime'][FIFO_HEADER]:
        raise ValueError('Stock FIFO header changed')
    generated[FIFO_HEADER] = adapt_header(original_header.decode()).encode()
    original_gx_state = (stock_export / 'nWiiRuntime' / GX_STATE_HEADER).read_bytes()
    if record(original_gx_state) != stock_manifest['runtime'][GX_STATE_HEADER]:
        raise ValueError('Stock GX state header changed')
    generated[GX_STATE_HEADER] = adapt_gx_state(original_gx_state.decode()).encode()
    generated['stock_texture_observation.h'] = texture_header(
        Path(__file__).resolve().parent, expected['textureHeader']).encode()
    if {name: record(data) for name, data in generated.items()} != expected['outputs']:
        raise RuntimeError('Active graphics runtime differs from verified Wii rev0')
    renderer = 'src/hle/gx/renderer_gl.cpp'
    generated[renderer] = adapt_renderer(generated[renderer])
    for name, transform in ((renderer, completion_batch.renderer),
            ('src/hle/gx/fifo_parser.cpp', completion_batch.parser),
            (FIFO_HEADER, completion_batch.header)):
        generated[name] = transform(generated[name].decode()).encode()
    if {name: record(generated[name]) for name in expected['completionBatchOutputs']} != expected['completionBatchOutputs']:
        raise RuntimeError('PE completion batching stage differs')
    generated[renderer] = depth_persistence(generated[renderer].decode()).encode()
    if {name: record(generated[name]) for name in expected['depthPersistenceOutputs']} != expected['depthPersistenceOutputs']:
        raise RuntimeError('EFB depth persistence stage differs')
    for name in expected['wiiAddressOutputs']:
        generated[name] = wii_address(generated[name], name)
    if {name: record(generated[name]) for name in expected['wiiAddressOutputs']} != expected['wiiAddressOutputs']:
        raise RuntimeError('Wii EFB address stage differs')
    texture_cache_header = 'include/runtime/texture_cache_gl.h'
    original_texture_cache = (stock_export / 'nWiiRuntime' / texture_cache_header).read_bytes()
    if record(original_texture_cache) != stock_manifest['runtime'][texture_cache_header]:
        raise ValueError('Stock texture cache header changed')
    generated[texture_cache_header] = indexed_view.header(original_texture_cache.decode()).encode()
    for name, transform in ((renderer, indexed_view.renderer),
            ('src/hle/texture_cache_gl.cpp', indexed_view.texture)):
        generated[name] = transform(generated[name].decode()).encode()
    if {name: record(generated[name]) for name in expected['indexedViewOutputs']} != expected['indexedViewOutputs']:
        raise RuntimeError('Indexed EFB view stage differs')
    for name, transform in (('src/hle/gx/fifo_parser.cpp', snapshot_timing.parser),
            ('src/hle/gx.cpp', snapshot_timing.gx)):
        generated[name] = transform(generated[name].decode()).encode()
    if {name: record(generated[name]) for name in expected['snapshotTimingOutputs']} != expected['snapshotTimingOutputs']:
        raise RuntimeError('GX snapshot timing stage differs')
    parser_path = 'src/hle/gx/fifo_parser.cpp'
    generated[parser_path] = vertex_size.parser(generated[parser_path].decode()).encode()
    if {parser_path: record(generated[parser_path])} != expected['vertexSizeOutputs']:
        raise RuntimeError('GX vertex size reuse stage differs')
    gx_path = 'src/hle/gx.cpp'
    generated[gx_path] = command_workspace.gx(generated[gx_path].decode()).encode()
    if {gx_path: record(generated[gx_path])} != expected['commandWorkspaceOutputs']:
        raise RuntimeError('GX command workspace reuse stage differs')
    generated[gx_path] = phase_profile.gx(generated[gx_path].decode()).encode()
    if {gx_path: record(generated[gx_path])} != expected['profileWindowOutputs']:
        raise RuntimeError('GX profile window stage differs')
    generated[renderer] = vertex_hotpath.renderer(generated[renderer].decode()).encode()
    if {renderer: record(generated[renderer])} != expected['vertexHotpathOutputs']:
        raise RuntimeError('GX vertex hotpath stage differs')
    destination.mkdir(mode=0o700)
    for name, data in generated.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    report = {'result': 'OWNER_WII_ACTIVE_GRAPHICS_RUNTIME_SOURCES_REPRODUCED_NOT_GAME_BUILD',
        'dolSha256': digest(dol_path), 'manifestSha256': digest(MANIFEST),
        'outputs': {name: record(data) for name, data in generated.items()},
        'limits': ['GX, renderer and texture behavior contain PC adaptations.',
            'Image fidelity, FPS and full game acceptance remain unverified.',
            'Only Wii US R5WEA4 revision 0 has been verified.']}
    (destination / 'recovery-result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--stock-export', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    print(recover(args.game_data, args.stock_export, args.destination)['result'])


if __name__ == '__main__':
    main()

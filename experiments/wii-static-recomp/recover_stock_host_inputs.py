"""Reproduce active host link sources from a verified own-Wii stock export."""
from pathlib import Path
import argparse
import heapq
import json
import re
import shutil

from export_stock_wii_us_copy import digest
from recover_stock_late_adapter_guest import record
from stock_dispatch_patch import adapt_dispatch
from verify_wii_us_copy import audit_copy


MANIFEST = Path(__file__).with_name('stock-host-inputs-wii-us-r5wea4-rev0.json')


def apply_edits(text, edits):
    lines = text.splitlines(keepends=True)
    for edit in reversed(edits):
        start = edit['startLine']
        before = edit['old'].splitlines(keepends=True)
        after = edit['new'].splitlines(keepends=True)
        if start < 0 or lines[start:start + len(before)] != before:
            raise ValueError('Host patch site differs')
        lines[start:start + len(before)] = after
    return ''.join(lines)


def apply_pairs(text, pairs):
    for before, after in pairs:
        if text.count(before) != 1:
            raise ValueError('Host literal patch site differs')
        text = text.replace(before, after, 1)
    return text


def bounds_source(fixed, expected_records, expected_ranges):
    table = fixed.split('static const FuncBound g_func_bounds[] = {', 1)[1].split('};', 1)[0]
    records = []
    sentinel = False
    for line in table.splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(
            r'\s*\{(0x[0-9A-Fa-f]+|0), (0x[0-9A-Fa-f]+|0), '
            r'(func_[0-9A-Fa-f]+|nullptr)\},?\s*', line)
        if not match:
            raise ValueError('Bounds table syntax differs')
        start, end = (int(match[i], 0) for i in (1, 2))
        if start == 0:
            sentinel = True
            break
        if not start < end <= 0xFFFFFFFF:
            raise ValueError('Invalid bounds interval')
        records.append((start, end))
    if not sentinel or len(records) != expected_records:
        raise ValueError('Bounds table differs')
    events = {}
    for index, (start, end) in enumerate(records):
        events.setdefault(start, []).append(index)
        events.setdefault(end, [])
    points = sorted(events)
    active = []
    ranges = []
    for point, following in zip(points, points[1:]):
        for index in events[point]:
            heapq.heappush(active, index)
        while active and records[active[0]][1] <= point:
            heapq.heappop(active)
        if not active:
            continue
        index = active[0]
        if ranges and ranges[-1][1] == point and ranges[-1][2] == index:
            ranges[-1] = (ranges[-1][0], following, index)
        else:
            ranges.append((point, following, index))
    if len(ranges) != expected_ranges:
        raise ValueError('Bounds range count differs')
    return ('#include "stock_bounds_lookup.h"\nstatic const StockBoundsRange ranges[] = {\n' +
        ''.join(f'    {{0x{start:08X}, 0x{end:08X}, {index}}},\n'
            for start, end, index in ranges) +
        '};\nextern "C" uint32_t stock_lookup_bounds(uint32_t target) {\n'
        '    return stock_bounds_index(ranges, sizeof(ranges) / sizeof(ranges[0]), target);\n}\n')


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
            stock_result['dolSha256'] != digest(dol_path):
        raise ValueError('Stock host inputs do not match verified Wii US rev0 DATA')

    def read_stock(path, group):
        data = (stock_export / path).read_bytes()
        name = path.removeprefix('nWiiRuntime/') if group == 'runtime' else path
        if record(data) != stock_manifest[group][name]:
            raise ValueError(f'Stock source changed: {path}')
        return data

    main = apply_edits(read_stock('nWiiRuntime/src/core/main.cpp', 'runtime').decode(),
        expected['mainEdits'])
    dispatch = (Path(__file__).with_name('stock_dispatch_select.cpp').read_text())
    if record(dispatch.encode()) != expected['dispatchBase']:
        raise ValueError('Public dispatch source changed')
    dispatch = apply_pairs(dispatch, [expected['dispatchRename']])
    fixed, routes = adapt_dispatch(read_stock('main_output.cpp', 'guest').decode())
    if len(routes) != expected['dispatchRoutes'] or \
            record(fixed.encode()) != expected['adaptedFixed']:
        raise ValueError('Generated dispatch differs')
    fixed = apply_edits(fixed, expected['fixedEdits'])
    if record(fixed.encode()) != expected['preBoundsFixed']:
        raise ValueError('Pre-bounds host source differs')
    bounds = bounds_source(fixed, expected['boundsRecords'], expected['boundsRanges'])
    fixed = expected['dispatchInclude'] + apply_pairs(fixed, expected['dispatchPatches'])
    generated = {
        'main.cpp': main.encode(),
        'dispatch.cpp': dispatch.encode(),
        'fixed.cpp': fixed.encode(),
        'bounds.cpp': bounds.encode(),
        'functions.h': read_stock('functions.h', 'guest'),
    }
    if {name: record(data) for name, data in generated.items()} != expected['outputs']:
        raise RuntimeError('Active host sources differ from verified Wii rev0 recipe')
    destination.mkdir(mode=0o700)
    for name, data in generated.items():
        (destination / name).write_bytes(data)
    report = {'result': 'OWNER_WII_ACTIVE_HOST_SOURCES_REPRODUCED_NOT_GAME_BUILD',
        'dolSha256': digest(dol_path), 'manifestSha256': digest(MANIFEST),
        'outputs': {name: record(data) for name, data in generated.items()},
        'limits': ['Main, dispatch and bounds contain PC adaptations.',
            'FloatUtils, toolchain, SDL and graphics dependencies are separate inputs.',
            'Image, audio, FPS and full game acceptance remain unverified.',
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

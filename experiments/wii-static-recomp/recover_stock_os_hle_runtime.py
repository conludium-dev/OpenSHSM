"""Reproduce the retained OS HLE trace source from a verified own-Wii export."""
from pathlib import Path
import argparse
import json
import shutil

from export_stock_wii_us_copy import digest
from recover_stock_late_adapter_guest import record
from stock_thp_observation import adapt_thp_calls
from verify_wii_us_copy import audit_copy


MANIFEST = Path(__file__).with_name('stock-os-hle-runtime-wii-us-r5wea4-rev0.json')


def adapt(text):
    text = adapt_thp_calls(text)
    marker = '  if (!g_trace_only.empty() && !g_trace_only.count(func_addr)) return;'
    if text.count(marker) != 1:
        raise ValueError('OS HLE observer site differs')
    return '#include "stock_thp_queue_observation.h"\n' + text.replace(marker,
        marker + '\n  stock_thp_queue_observation::observe(ctx, func_addr);', 1)


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
    source = stock_export / 'nWiiRuntime/src/core/os_hle_stubs.cpp'
    dol_path = game / 'sys/main.dol'
    if expected['gameId'] != 'R5WEA4' or expected['revision'] != 0 or \
            expected['source'] != 'stock-export-wii-us-r5wea4-rev0.json' or \
            stock_result['result'] != 'OWNER_WII_US_R5WEA4_REV0_STOCK_SOURCE_EXPORTED_NOT_GAME_BUILD' or \
            stock_result['dolSha256'] != digest(dol_path) or \
            record(source.read_bytes()) != stock_manifest['runtime']['src/core/os_hle_stubs.cpp']:
        raise ValueError('Stock OS HLE source is not from verified Wii US rev0 export')
    data = adapt(source.read_text()).encode()
    if record(data) != expected['osHle']:
        raise RuntimeError('Active OS HLE trace source differs from verified Wii rev0')
    destination.mkdir(mode=0o700)
    (destination / 'os_hle_stubs.cpp').write_bytes(data)
    report = {'result': 'OWNER_WII_ACTIVE_OS_HLE_TRACE_SOURCE_REPRODUCED_NOT_RUNTIME_BUILD',
        'dolSha256': digest(dol_path), 'manifestSha256': digest(MANIFEST),
        'stockSourceSha256': digest(source), 'osHle': record(data),
        'limits': ['THP and queue observation are PC diagnostics.',
            'Full runtime archive, accurate OS services and game acceptance remain.',
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

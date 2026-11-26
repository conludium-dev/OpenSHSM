"""Copy active, unchanged runtime units from a verified own-Wii stock export."""
from pathlib import Path
import argparse
import json
import shutil

from export_stock_wii_us_copy import digest
from recover_stock_late_adapter_guest import record
from verify_wii_us_copy import audit_copy


MANIFEST = Path(__file__).with_name('stock-unchanged-runtime-wii-us-r5wea4-rev0.json')


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
        raise ValueError('Stock runtime does not match verified Wii US rev0 DATA')
    if len(expected['units']) != 22 or len({row['member'] for row in expected['units']}) != 22:
        raise ValueError('Unchanged runtime unit list differs')
    generated = {}
    for row in expected['units']:
        name = row['source']
        if not name.startswith('src/') or '..' in Path(name).parts or \
                Path(name).name + '.o' != row['member']:
            raise ValueError('Invalid unchanged runtime path')
        data = (stock_export / 'nWiiRuntime' / name).read_bytes()
        fingerprint = record(data)
        if fingerprint != stock_manifest['runtime'][name] or fingerprint != row['sourceFingerprint']:
            raise ValueError(f'Stock runtime source changed: {name}')
        generated[name] = data
    destination.mkdir(mode=0o700)
    for name, data in generated.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    report = {'result': 'OWNER_WII_ACTIVE_UNCHANGED_RUNTIME_SOURCES_REPRODUCED_NOT_RUNTIME_BUILD',
        'dolSha256': digest(dol_path), 'manifestSha256': digest(MANIFEST),
        'outputs': {name: record(data) for name, data in generated.items()},
        'limits': ['Source fingerprints match the pinned stock export; owner compilation flags may differ.',
            'Other runtime members, full game and other Wii regions remain unverified.']}
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

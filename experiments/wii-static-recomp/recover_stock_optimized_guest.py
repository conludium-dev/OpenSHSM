"""Reproduce the first guest lowering stage from an owner-supplied stock export."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

from export_stock_wii_us_copy import verify_export
from stock_byte_reverse_patch import lower_byte_reverse
from stock_logical_record_patch import lower_logical_record
from stock_psq_patch import lower_indexed
from verify_wii_us_copy import audit_copy


MANIFEST = Path(__file__).with_name('stock-optimized-wii-us-r5wea4-rev0.json')


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


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

    verify_export(stock_export)
    export_result = json.loads((stock_export.parent / 'export-result.json').read_text())
    if export_result['result'] != 'OWNER_WII_US_R5WEA4_REV0_STOCK_SOURCE_EXPORTED_NOT_GAME_BUILD' or \
            Path(export_result['output']).resolve(strict=True) != stock_export or \
            export_result['dolSha256'] != digest(game / 'sys/main.dol'):
        raise ValueError('Stock export does not match the verified Wii DATA')
    expected = json.loads(MANIFEST.read_text())
    if expected['gameId'] != 'R5WEA4' or expected['revision'] != 0 or \
            set(expected['units']) != {f'output_{index}.cpp' for index in range(75)}:
        raise ValueError('Unexpected optimized guest manifest')
    if shutil.disk_usage(destination.parent).free < 512 * 1024 * 1024:
        raise ValueError('Insufficient free space for recovered guest source')

    dol = (game / 'sys/main.dol').read_bytes()
    destination.mkdir(mode=0o700)
    rows = {}
    for index in range(75):
        name = f'output_{index}.cpp'
        text = (stock_export / name).read_text()
        text, psq = lower_indexed(text, dol)
        text, reverse = lower_byte_reverse(text, dol)
        text, logical = lower_logical_record(text, dol)
        data = text.encode()
        actual = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
            'psqSites': len(psq), 'byteReverseSites': len(reverse),
            'logicalRecordSites': len(logical)}
        if actual != expected['units'][name]:
            raise RuntimeError(f'Optimized guest lowering differs from verified Wii rev0: {name}')
        (destination / name).write_bytes(data)
        rows[name] = actual

    report = {'result': 'OWNER_WII_STOCK_OPTIMIZED_GUEST_SOURCE_REPRODUCED_NOT_GAME_BUILD',
        'gameData': str(game), 'stockExport': str(stock_export),
        'stockManifestSha256': digest(Path(__file__).with_name(expected['source'])),
        'optimizedManifestSha256': digest(MANIFEST),
        'dolSha256': digest(game / 'sys/main.dol'),
        'units': rows,
        'limits': ['Generated guest source is private and must not enter a public package.',
            'This is only the first guest lowering stage; later guest and runtime patches remain.',
            'Only Wii US R5WEA4 revision 0 has been verified.']}
    (destination / 'recovery-result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--stock-export', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    report = recover(args.game_data, args.stock_export, args.destination)
    print(report['result'], len(report['units']))


if __name__ == '__main__':
    main()

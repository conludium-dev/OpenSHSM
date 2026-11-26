"""Reproduce the InputManager snapshot adapter from a verified Wii stock export."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

from export_stock_wii_us_copy import STOCK_MANIFEST, digest, verify_export
from stock_input_snapshot_patch import adapt
from verify_wii_us_copy import audit_copy


MANIFEST = Path(__file__).with_name('stock-input-snapshot-runtime-wii-us-r5wea4-rev0.json')


def record(data):
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


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
    if shutil.disk_usage(destination.parent).free < 64 * 1024 * 1024:
        raise ValueError('Insufficient free space for recovered runtime source')

    stock_manifest, _, runtime_files = verify_export(stock_export)
    expected = json.loads(MANIFEST.read_text())
    if expected['gameId'] != 'R5WEA4' or expected['revision'] != 0 or \
            expected['source'] != STOCK_MANIFEST.name or \
            stock_manifest['gameId'] != expected['gameId'] or \
            stock_manifest['revision'] != expected['revision']:
        raise ValueError('Stock runtime does not match Wii US rev0')
    root = stock_export / 'nWiiRuntime'
    names = ('include/input/input_manager.h', 'src/input/input_manager.cpp')
    for name in names:
        if record((root / name).read_bytes()) != runtime_files[name]:
            raise RuntimeError(f'Stock runtime source changed: {name}')
    header, source = adapt((root / names[0]).read_text(),
        (root / names[1]).read_text())
    outputs = {'include/input/input_manager.h': header.encode(),
        'src/input/input_manager.cpp': source.encode()}
    if {name: record(data) for name, data in outputs.items()} != expected['outputs']:
        raise RuntimeError('InputManager adapter differs from verified Wii rev0 stage')

    destination.mkdir(mode=0o700)
    for name, data in outputs.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    report = {'result': 'OWNER_WII_INPUT_SNAPSHOT_RUNTIME_SOURCES_REPRODUCED_NOT_GAME_BUILD',
        'gameData': str(game), 'stockExport': str(stock_export),
        'dolSha256': digest(game / 'sys/main.dol'),
        'stockManifestSha256': digest(STOCK_MANIFEST),
        'manifestSha256': digest(MANIFEST), 'outputs': expected['outputs'],
        'limits': ['InputSnapshot queue and mutex are native runtime adaptations, not Wii behavior.',
            'Other runtime changes, compilation, linking and controller acceptance remain.',
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
    print(report['result'], len(report['outputs']))


if __name__ == '__main__':
    main()

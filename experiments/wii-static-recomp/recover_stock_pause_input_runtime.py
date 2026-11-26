"""Reproduce the active PC pause-input sources from own-Wii runtime stages."""
from pathlib import Path
import argparse
import json
import shutil

from export_stock_wii_us_copy import digest
from recover_stock_late_adapter_guest import record
from stock_hidden_input_patch import adapt as hidden_keyboard
from stock_pause_input_patch import gamepad, keyboard, manager, manager_header
from verify_wii_us_copy import audit_copy


MANIFEST = Path(__file__).with_name('stock-pause-input-runtime-wii-us-r5wea4-rev0.json')
SOURCES = {
    'mouse_keyboard_source.cpp': ('src/input/sources/mouse_keyboard_source.cpp',
        lambda text: hidden_keyboard(keyboard(text))),
    'gamepad_source.cpp': ('src/input/sources/gamepad_source.cpp', gamepad),
}


def recover(game_data, stock_export, snapshot_runtime, destination):
    game = Path(audit_copy(game_data)['source']).resolve(strict=True)
    stock_export = Path(stock_export).expanduser().resolve(strict=True)
    snapshot_runtime = Path(snapshot_runtime).expanduser().resolve(strict=True)
    destination = Path(destination).expanduser().absolute()
    if not destination.parent.is_dir():
        raise ValueError('Destination parent does not exist')
    destination = destination.parent.resolve(strict=True) / destination.name
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destination must be a fresh directory')
    if any(destination == source or source in destination.parents
            for source in (game, stock_export, snapshot_runtime)):
        raise ValueError('Destination must be outside inputs')
    if shutil.disk_usage(destination.parent).free < 16 * 1024 * 1024:
        raise ValueError('Insufficient free space')

    expected = json.loads(MANIFEST.read_text())
    stock_manifest = json.loads(Path(__file__).with_name(
        'stock-export-wii-us-r5wea4-rev0.json').read_text())
    snapshot_manifest_path = Path(__file__).with_name(
        'stock-input-snapshot-runtime-wii-us-r5wea4-rev0.json')
    snapshot_manifest = json.loads(snapshot_manifest_path.read_text())
    stock_result = json.loads((stock_export.parent / 'export-result.json').read_text())
    snapshot_result = json.loads((snapshot_runtime / 'recovery-result.json').read_text())
    dol_path = game / 'sys/main.dol'
    if expected['gameId'] != 'R5WEA4' or expected['revision'] != 0 or \
            stock_result['result'] != 'OWNER_WII_US_R5WEA4_REV0_STOCK_SOURCE_EXPORTED_NOT_GAME_BUILD' or \
            stock_result['dolSha256'] != digest(dol_path) or \
            snapshot_result['result'] != 'OWNER_WII_INPUT_SNAPSHOT_RUNTIME_SOURCES_REPRODUCED_NOT_GAME_BUILD' or \
            snapshot_result['dolSha256'] != digest(dol_path) or \
            snapshot_result['manifestSha256'] != digest(snapshot_manifest_path) or \
            snapshot_result['outputs'] != snapshot_manifest['outputs']:
        raise ValueError('Input stages do not match verified Wii US rev0 DATA')

    generated = {}
    for name, (relative, adapter) in SOURCES.items():
        original = (stock_export / 'nWiiRuntime' / relative).read_bytes()
        if record(original) != stock_manifest['runtime'][relative]:
            raise ValueError(f'Stock input source changed: {name}')
        generated[name] = adapter(original.decode()).encode()
    for name, adapter in (('src/input/input_manager.cpp', manager),
            ('include/input/input_manager.h', manager_header)):
        original = (snapshot_runtime / name).read_bytes()
        if record(original) != snapshot_manifest['outputs'][name]:
            raise ValueError(f'Input snapshot stage changed: {name}')
        generated[name] = adapter(original.decode()).encode()
    if set(generated) != set(expected['files']):
        raise ValueError('Pause input manifest file list differs')
    for name, data in generated.items():
        if record(data) != expected['files'][name]:
            raise RuntimeError(f'Active pause input differs from verified Wii rev0: {name}')

    destination.mkdir(mode=0o700)
    for name, data in generated.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    report = {'result': 'OWNER_WII_ACTIVE_PAUSE_INPUT_SOURCES_REPRODUCED_NOT_RUNTIME_BUILD',
        'dolSha256': digest(dol_path), 'manifestSha256': digest(MANIFEST),
        'files': {name: record(data) for name, data in generated.items()},
        'limits': ['Pause mapping and snapshot queue are PC input adapters.',
            'Physical controller acceptance and full runtime build remain.',
            'Only Wii US R5WEA4 revision 0 has been verified.']}
    (destination / 'recovery-result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--stock-export', type=Path, required=True)
    parser.add_argument('--snapshot-runtime', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    print(recover(args.game_data, args.stock_export,
        args.snapshot_runtime, args.destination)['result'])


if __name__ == '__main__':
    main()

"""Reproduce desktop Wii input adapters from the verified pause-input stage."""
from pathlib import Path
import argparse
import json
import shutil

from export_stock_wii_us_copy import digest
from recover_stock_late_adapter_guest import record
from stock_desktop_input_patch import keyboard, gamepad, roll, controller_motion
import stock_desktop_look_patch as desktop_look
from verify_wii_us_copy import audit_copy


MANIFEST = Path(__file__).with_name('stock-desktop-input-runtime-wii-us-r5wea4-rev0.json')
PAUSE_MANIFEST = Path(__file__).with_name('stock-pause-input-runtime-wii-us-r5wea4-rev0.json')
ADAPTERS = {'mouse_keyboard_source.cpp': keyboard, 'gamepad_source.cpp': gamepad}


def recover(game_data, stock_export, pause_runtime, destination):
    game = Path(audit_copy(game_data)['source']).resolve(strict=True)
    stock_export = Path(stock_export).expanduser().resolve(strict=True)
    pause_runtime = Path(pause_runtime).expanduser().resolve(strict=True)
    destination = Path(destination).expanduser().absolute()
    if not destination.parent.is_dir():
        raise ValueError('Destination parent does not exist')
    destination = destination.parent.resolve(strict=True) / destination.name
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destination must be a fresh directory')
    if any(destination == source or source in destination.parents
            for source in (game, stock_export, pause_runtime)):
        raise ValueError('Destination must be outside inputs')
    if shutil.disk_usage(destination.parent).free < 16 * 1024 * 1024:
        raise ValueError('Insufficient free space')

    expected = json.loads(MANIFEST.read_text())
    pause_expected = json.loads(PAUSE_MANIFEST.read_text())
    pause_report = json.loads((pause_runtime / 'recovery-result.json').read_text())
    stock_report = json.loads((stock_export.parent / 'export-result.json').read_text())
    dol_sha = digest(game / 'sys/main.dol')
    if expected['gameId'] != 'R5WEA4' or expected['revision'] != 0 or \
            expected['source'] != PAUSE_MANIFEST.name or \
            pause_report['result'] != 'OWNER_WII_ACTIVE_PAUSE_INPUT_SOURCES_REPRODUCED_NOT_RUNTIME_BUILD' or \
            pause_report['dolSha256'] != dol_sha or \
            pause_report['manifestSha256'] != digest(PAUSE_MANIFEST) or \
            pause_report['files'] != pause_expected['files'] or \
            stock_report['dolSha256'] != dol_sha:
        raise ValueError('Desktop input source stages differ from verified Wii US rev0')

    generated = {}
    for name, fingerprint in pause_expected['files'].items():
        original = (pause_runtime / name).read_bytes()
        if record(original) != fingerprint:
            raise ValueError(f'Pause input differs: {name}')
        generated[name] = ADAPTERS[name](original.decode()).encode() if name in ADAPTERS else original
    if set(generated) != set(expected['files']):
        raise ValueError('Desktop input file list differs')
    for name, data in generated.items():
        if record(data) != expected['files'][name]:
            raise RuntimeError(f'Desktop input differs from verified adapter: {name}')

    generated['mouse_keyboard_source.cpp'] = roll(generated['mouse_keyboard_source.cpp'].decode()).encode()
    generated['gamepad_source.cpp'] = controller_motion(generated['gamepad_source.cpp'].decode()).encode()
    if {name: record(generated[name]) for name in expected['motionOutputs']} != expected['motionOutputs']:
        raise RuntimeError('Desktop motion stage differs')

    look_adapters = {'mouse_keyboard_source.cpp': desktop_look.keyboard,
        'gamepad_source.cpp': desktop_look.gamepad,
        'src/input/input_manager.cpp': desktop_look.manager,
        'include/input/input_manager.h': desktop_look.manager_header}
    for name, adapter in look_adapters.items():
        generated[name] = adapter(generated[name].decode()).encode()
    if {name: record(generated[name]) for name in look_adapters} != expected['lookOutputs']:
        raise RuntimeError('Desktop look snapshot stage differs')

    destination.mkdir(mode=0o700)
    for name, data in generated.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    report = {'result': 'OWNER_WII_DESKTOP_INPUT_SOURCES_REPRODUCED_NOT_RUNTIME_BUILD',
        'dolSha256': dol_sha, 'manifestSha256': digest(MANIFEST),
        'files': {name: record(data) for name, data in generated.items()},
        'limits': ['Mouse, keyboard and standard gamepad mappings are PC input adapters.',
            'Physical Wiimote, motion gestures and full-game acceptance remain unverified.',
            'Only Wii US R5WEA4 revision 0 has been verified.']}
    (destination / 'recovery-result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--stock-export', type=Path, required=True)
    parser.add_argument('--pause-runtime', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    print(recover(args.game_data, args.stock_export,
        args.pause_runtime, args.destination)['result'])


if __name__ == '__main__':
    main()

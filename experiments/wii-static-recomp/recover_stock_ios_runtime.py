"""Reproduce the active IOS callback source from verified own-Wii runtime."""
from pathlib import Path
import argparse
import json
import shutil

from export_stock_wii_us_copy import digest
from recover_stock_late_adapter_guest import record
from verify_wii_us_copy import audit_copy


MANIFEST = Path(__file__).with_name('stock-ios-runtime-wii-us-r5wea4-rev0.json')
SOURCE = 'src/hle/ios.cpp'


def apply_observer_stage(text, edits):
    lines = text.splitlines(keepends=True)
    for edit in reversed(edits):
        start = edit['startLine']
        before = edit['old'].splitlines(keepends=True)
        after = edit['new'].splitlines(keepends=True)
        if start < 0 or lines[start:start + len(before)] != before:
            raise ValueError('IOS observer stage patch site differs')
        lines[start:start + len(before)] = after
    return ''.join(lines)


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
    original = (stock_export / 'nWiiRuntime' / SOURCE).read_bytes()
    if record(original) != stock_manifest['runtime'][SOURCE]:
        raise ValueError('Stock IOS source changed')
    if len(expected['observerEdits']) != 17:
        raise ValueError('IOS observer stage edit list differs')
    text = apply_observer_stage(original.decode(), expected['observerEdits'])
    if record(text.encode()) != expected['stages']['observer']:
        raise RuntimeError('IOS observer stage differs')
    for name in ('decEeGate', 'viBusyLatch', 'hardwareWhileCallback', 'callbackSampleCache'):
        before, after = expected['patches'][name]
        if text.count(before) != 1:
            raise ValueError(f'IOS {name} patch site differs')
        text = text.replace(before, after, 1)
        if record(text.encode()) != expected['stages'][name]:
            raise RuntimeError(f'IOS {name} stage differs')
    data = text.encode()
    destination.mkdir(mode=0o700)
    path = destination / SOURCE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    report = {'result': 'OWNER_WII_ACTIVE_IOS_RUNTIME_SOURCE_REPRODUCED_NOT_GAME_BUILD',
        'dolSha256': digest(dol_path), 'manifestSha256': digest(MANIFEST),
        'output': record(data),
        'limits': ['Callback scheduling, observations and FP context handling are PC runtime adaptations.',
            'Only Wii US R5WEA4 revision 0 has been verified.',
            'Full guest thread/IRQ behavior and game acceptance remain unverified.']}
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

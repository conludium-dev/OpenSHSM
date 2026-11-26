"""Reproduce HID2 and carry guest lowerings from a verified owner-only stage."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

from carry_lowering import lower as lower_carry
from recover_stock_optimized_guest import digest
from stock_hid2_guest_patch import lower_hid2
from verify_wii_us_copy import audit_copy


MANIFEST = Path(__file__).with_name('stock-hid2-carry-wii-us-r5wea4-rev0.json')


def recover(game_data, optimized_guest, destination):
    game = Path(audit_copy(game_data)['source']).resolve(strict=True)
    optimized_guest = Path(optimized_guest).expanduser().resolve(strict=True)
    destination = Path(destination).expanduser().absolute()
    if not destination.parent.is_dir():
        raise ValueError('Destination parent does not exist')
    destination = destination.parent.resolve(strict=True) / destination.name
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destination must be a fresh directory')
    if any(destination == source or source in destination.parents
            for source in (game, optimized_guest)):
        raise ValueError('Destination must be outside Wii DATA and prior guest stage')
    if shutil.disk_usage(destination.parent).free < 512 * 1024 * 1024:
        raise ValueError('Insufficient free space for recovered guest source')

    expected = json.loads(MANIFEST.read_text())
    previous_manifest = Path(__file__).with_name(expected['source'])
    previous = json.loads(previous_manifest.read_text())
    previous_result = json.loads((optimized_guest / 'recovery-result.json').read_text())
    if expected['gameId'] != 'R5WEA4' or expected['revision'] != 0 or \
            set(expected['units']) != {f'output_{index}.cpp' for index in range(75)} or \
            previous_result['result'] != 'OWNER_WII_STOCK_OPTIMIZED_GUEST_SOURCE_REPRODUCED_NOT_GAME_BUILD' or \
            previous_result['dolSha256'] != digest(game / 'sys/main.dol') or \
            previous_result['optimizedManifestSha256'] != digest(previous_manifest) or \
            previous_result['units'] != previous['units']:
        raise ValueError('Optimized guest stage does not match the verified Wii DATA')

    dol = (game / 'sys/main.dol').read_bytes()
    destination.mkdir(mode=0o700)
    rows = {}
    for index in range(75):
        name = f'output_{index}.cpp'
        source = optimized_guest / name
        if source.stat().st_size != previous['units'][name]['bytes'] or \
                digest(source) != previous['units'][name]['sha256']:
            raise RuntimeError(f'Optimized guest source changed: {name}')
        text, hid2 = lower_hid2(source.read_text(), dol)
        text, carry = lower_carry(text, dol, stock=True)
        data = text.encode()
        actual = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
            'hid2Sites': len(hid2), 'carrySites': len(carry)}
        if actual != expected['units'][name]:
            raise RuntimeError(f'HID2/carry guest lowering differs from verified Wii rev0: {name}')
        (destination / name).write_bytes(data)
        rows[name] = actual

    report = {'result': 'OWNER_WII_HID2_CARRY_GUEST_SOURCE_REPRODUCED_NOT_GAME_BUILD',
        'gameData': str(game), 'optimizedGuest': str(optimized_guest),
        'previousResultSha256': digest(optimized_guest / 'recovery-result.json'),
        'manifestSha256': digest(MANIFEST), 'dolSha256': digest(game / 'sys/main.dol'),
        'units': rows,
        'limits': ['Generated guest source is private and must not enter a public package.',
            'Later guest stages, processor runtime adapter and full build remain.',
            'Only Wii US R5WEA4 revision 0 has been verified.']}
    (destination / 'recovery-result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--optimized-guest', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    report = recover(args.game_data, args.optimized_guest, args.destination)
    print(report['result'], len(report['units']))


if __name__ == '__main__':
    main()

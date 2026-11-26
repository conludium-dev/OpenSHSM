"""Reproduce paired-estimate guest inputs from the verified Wii transition stage."""
from pathlib import Path
import argparse
import json
import shutil

from export_stock_wii_us_copy import digest
from recover_stock_late_adapter_guest import record
from stock_input_sdk_patch import adapt as input_sdk
from stock_paired_estimate_patch import adapt as paired_estimate
from stock_scan_consumption import adapt_caller as scan_caller
from verify_wii_us_copy import audit_copy


MANIFEST = Path(__file__).with_name('stock-paired-guest-wii-us-r5wea4-rev0.json')


def adapt(text, dol, index):
    if index == 1:
        text = input_sdk(text, 'output_1.cpp')
    if index == 19:
        text = scan_caller(text, dol)
    return paired_estimate(text, dol)


def recover(game_data, guest38, destination):
    game = Path(audit_copy(game_data)['source']).resolve(strict=True)
    guest38 = Path(guest38).expanduser().resolve(strict=True)
    destination = Path(destination).expanduser().absolute()
    if not destination.parent.is_dir():
        raise ValueError('Destination parent does not exist')
    destination = destination.parent.resolve(strict=True) / destination.name
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destination must be a fresh directory')
    if any(destination == source or source in destination.parents
            for source in (game, guest38)):
        raise ValueError('Destination must be outside Wii DATA and prior guest stage')
    if shutil.disk_usage(destination.parent).free < 512 * 1024 * 1024:
        raise ValueError('Insufficient free space for recovered guest source')

    expected = json.loads(MANIFEST.read_text())
    previous_manifest = Path(__file__).with_name(expected['source'])
    previous = json.loads(previous_manifest.read_text())
    previous_result = json.loads((guest38 / 'recovery-result.json').read_text())
    changed = {1, 2, 4, 5, 6, 7, 8, 12, 14, 15, 19,
        20, 21, 22, 23, 24, 25, 26, 27, 28, 29}
    if expected['gameId'] != 'R5WEA4' or expected['revision'] != 0 or \
            expected['changedUnits'] != [f'output_{index}.cpp' for index in sorted(changed)] or \
            set(expected['units']) != {f'output_{index}.cpp' for index in range(75)} or \
            previous_result['result'] != 'OWNER_WII_GUEST38_TRANSITION_REPRODUCED_NOT_GAME_BUILD' or \
            previous_result['dolSha256'] != digest(game / 'sys/main.dol') or \
            previous_result['manifestSha256'] != digest(previous_manifest) or \
            previous_result['units'] != previous['units']:
        raise ValueError('Guest38 stage does not match the verified Wii DATA')

    dol = (game / 'sys/main.dol').read_bytes()
    destination.mkdir(mode=0o700)
    units = {}
    total_sites = 0
    for index in range(75):
        name = f'output_{index}.cpp'
        source = guest38 / name
        original = source.read_bytes()
        if record(original) != previous['units'][name]:
            raise RuntimeError(f'Guest38 source changed: {name}')
        sites = []
        if index in changed:
            text, sites = adapt(original.decode(), dol, index)
            data = text.encode()
        else:
            data = original
        actual = {**record(data), 'pairedEstimateSites': len(sites)}
        if actual != expected['units'][name]:
            raise RuntimeError(f'Paired guest lowering differs from verified Wii rev0: {name}')
        (destination / name).write_bytes(data)
        units[name] = actual
        total_sites += len(sites)
    if total_sites != expected['totalPairedEstimateSites']:
        raise RuntimeError('Paired estimate site total changed')

    report = {'result': 'OWNER_WII_PAIRED_GUEST_SOURCES_REPRODUCED_NOT_GAME_BUILD',
        'gameData': str(game), 'guest38': str(guest38),
        'dolSha256': digest(game / 'sys/main.dol'),
        'manifestSha256': digest(MANIFEST), 'units': units,
        'changedUnits': expected['changedUnits'],
        'pairedEstimateSites': total_sites,
        'limits': ['Generated guest source is private and must not enter a public package.',
            'PC input and scan observation hooks are native adapters; estimate instructions are Wii DOL verified.',
            'Runtime, compilation, linking and full game acceptance remain.',
            'Only Wii US R5WEA4 revision 0 has been verified.']}
    (destination / 'recovery-result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--guest38', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    report = recover(args.game_data, args.guest38, args.destination)
    print(report['result'], len(report['units']), report['pairedEstimateSites'])


if __name__ == '__main__':
    main()

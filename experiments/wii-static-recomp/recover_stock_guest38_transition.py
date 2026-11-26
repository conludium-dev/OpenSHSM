"""Reproduce the active THP/syscall guest unit from the verified late Wii stage."""
from pathlib import Path
import argparse
import json
import shutil

from export_stock_wii_us_copy import digest
from recover_stock_late_adapter_guest import record
from stock_dcbz_lowering import lower_dcbz
from stock_sc_pc_patch import adapt as lower_sc_pc
from verify_wii_us_copy import audit_copy


MANIFEST = Path(__file__).with_name('stock-guest38-transition-wii-us-r5wea4-rev0.json')


def adapt(text, dol):
    text, sc_sites = lower_sc_pc(text, dol)
    if sc_sites != [0x802106F0, 0x80212FF8, 0x80213028]:
        raise ValueError('Wii syscall PC sites changed')
    text, dcbz_sites = lower_dcbz(text, dol, expected_sites=1)
    if dcbz_sites[0]['address'] != 0x8021307C:
        raise ValueError('Wii THP dcbz site changed')
    marker = 'loc_80212FF4: ;\n'
    end_marker = 'loc_80212FF8: ;'
    if text.count(marker) != 1 or text.count(end_marker) != 1:
        raise ValueError('Wii cache IRQ loop changed')
    start = text.index(marker)
    end = text.index(end_marker, start)
    fragment = text[start:end]
    anchor = '    if (process_pending_callbacks(ctx)) return;'
    if fragment.count(anchor) != 1:
        raise ValueError('Wii callback anchor changed')
    fragment = fragment.replace(anchor,
        '    openshsm::experiment::observe_cache_irq(ctx, 4);\n' + anchor +
        '\n    openshsm::experiment::observe_cache_irq(ctx, 5);')
    text = text[:start] + fragment + text[end:]
    text = '#include "stock_cache_irq_observation.h"\n' + \
        '#include "stock_context_observation.h"\n' + text
    return text, sc_sites, dcbz_sites


def recover(game_data, late_guest, destination):
    game = Path(audit_copy(game_data)['source']).resolve(strict=True)
    late_guest = Path(late_guest).expanduser().resolve(strict=True)
    destination = Path(destination).expanduser().absolute()
    if not destination.parent.is_dir():
        raise ValueError('Destination parent does not exist')
    destination = destination.parent.resolve(strict=True) / destination.name
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destination must be a fresh directory')
    if any(destination == source or source in destination.parents
            for source in (game, late_guest)):
        raise ValueError('Destination must be outside Wii DATA and prior guest stage')
    if shutil.disk_usage(destination.parent).free < 512 * 1024 * 1024:
        raise ValueError('Insufficient free space for recovered guest source')

    expected = json.loads(MANIFEST.read_text())
    previous_manifest = Path(__file__).with_name(expected['source'])
    previous = json.loads(previous_manifest.read_text())
    previous_result = json.loads((late_guest / 'recovery-result.json').read_text())
    if expected['gameId'] != 'R5WEA4' or expected['revision'] != 0 or \
            expected['changedUnit'] != 'output_38.cpp' or \
            set(expected['units']) != {f'output_{index}.cpp' for index in range(75)} or \
            previous_result['result'] != 'OWNER_WII_SELECTED_LATE_GUEST_ADAPTERS_REPRODUCED_NOT_GAME_BUILD' or \
            previous_result['dolSha256'] != digest(game / 'sys/main.dol') or \
            previous_result['manifestSha256'] != digest(previous_manifest) or \
            previous_result['units'] != previous['units']:
        raise ValueError('Late guest stage does not match the verified Wii DATA')

    dol = (game / 'sys/main.dol').read_bytes()
    destination.mkdir(mode=0o700)
    units = {}
    sc_sites = []
    dcbz_sites = []
    for index in range(75):
        name = f'output_{index}.cpp'
        source = late_guest / name
        original = source.read_bytes()
        if record(original) != previous['units'][name]:
            raise RuntimeError(f'Late guest source changed: {name}')
        if index == 38:
            text, sc_sites, dcbz_sites = adapt(original.decode(), dol)
            data = text.encode()
        else:
            data = original
        actual = record(data)
        if actual != expected['units'][name]:
            raise RuntimeError(f'Guest38 transition differs from verified Wii rev0: {name}')
        (destination / name).write_bytes(data)
        units[name] = actual

    report = {'result': 'OWNER_WII_GUEST38_TRANSITION_REPRODUCED_NOT_GAME_BUILD',
        'gameData': str(game), 'lateGuest': str(late_guest),
        'dolSha256': digest(game / 'sys/main.dol'),
        'manifestSha256': digest(MANIFEST), 'units': units,
        'syscallPcSites': [hex(address) for address in sc_sites],
        'thpDcbzSite': hex(dcbz_sites[0]['address']),
        'limits': ['Generated guest source is private and must not enter a public package.',
            'Cache IRQ observation is diagnostic; syscall PC and dcbz are Wii instruction fixes.',
            'Runtime, compilation, linking and full game acceptance remain.',
            'Only Wii US R5WEA4 revision 0 has been verified.']}
    (destination / 'recovery-result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--late-guest', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    report = recover(args.game_data, args.late_guest, args.destination)
    print(report['result'], len(report['units']))


if __name__ == '__main__':
    main()

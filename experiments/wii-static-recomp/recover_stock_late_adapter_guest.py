"""Reproduce selected late guest adapters from the verified Wii FP source stage."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import struct

from recover_stock_optimized_guest import digest
from stock_input_sdk_patch import adapt as input_sdk
from stock_loading_observation import adapt as loading
from stock_subtitle_progress import adapt as subtitle
from verify_wii_us_copy import audit_copy


MANIFEST = Path(__file__).with_name('stock-late-adapters-wii-us-r5wea4-rev0.json')


def record(data):
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def dol_word(dol, address):
    layout = struct.unpack('>64I', dol[:256])
    section = next(i for i in range(18) if layout[18 + i] <= address
        and address + 4 <= layout[18 + i] + layout[36 + i])
    offset = layout[section] + address - layout[18 + section]
    return struct.unpack_from('>I', dol, offset)[0]


def insert_after(text, marker, insertion, count=1):
    if text.count(marker) != count:
        raise ValueError(f'Guest marker count changed: {marker.strip()}')
    return text.replace(marker, marker + insertion)


def adapt(text, dol, index):
    if index == 16:
        return subtitle(text, dol)
    if index in (30, 32):
        return loading(text, dol, index, payloads=True)
    if index == 44:
        return input_sdk(text, 'output_44.cpp')
    if index == 18:
        if dol_word(dol, 0x80100568) != 0x800F0010:
            raise ValueError('Wii PC boot hook opcode changed')
        text = insert_after(text, 'loc_80100568: ;\n',
            '    openshsm::experiment::skip_pc_boot_notices(ctx);\n', 9)
        return '#include "stock_pc_boot_notices.h"\n' + text
    if index == 40:
        text = insert_after(text, 'loc_80241E08: ;\n',
            '    openshsm::experiment::observe_ipc_vector(ctx);\n')
        return '#include "stock_ipc_vector_observation.h"\n' + text
    if index == 64:
        for label, entry in (('8035AEF8', 'true'), ('8035AF34', 'false')):
            text = insert_after(text, f'loc_{label}: ;\n',
                f'    openshsm::experiment::observe_buffer_flush(ctx, {entry});\n')
        return '#include "stock_buffer_flush_observation.h"\n' + text
    return text


def recover(game_data, fp_guest, destination):
    game = Path(audit_copy(game_data)['source']).resolve(strict=True)
    fp_guest = Path(fp_guest).expanduser().resolve(strict=True)
    destination = Path(destination).expanduser().absolute()
    if not destination.parent.is_dir():
        raise ValueError('Destination parent does not exist')
    destination = destination.parent.resolve(strict=True) / destination.name
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destination must be a fresh directory')
    if any(destination == source or source in destination.parents
            for source in (game, fp_guest)):
        raise ValueError('Destination must be outside Wii DATA and prior guest stage')
    if shutil.disk_usage(destination.parent).free < 512 * 1024 * 1024:
        raise ValueError('Insufficient free space for recovered guest source')

    expected = json.loads(MANIFEST.read_text())
    previous_manifest = Path(__file__).with_name(expected['source'])
    previous = json.loads(previous_manifest.read_text())
    previous_result = json.loads((fp_guest / 'recovery-result.json').read_text())
    if expected['gameId'] != 'R5WEA4' or expected['revision'] != 0 or \
            set(expected['units']) != {f'output_{index}.cpp' for index in range(75)} or \
            previous_result['result'] != 'OWNER_WII_FP_GUARD_GUEST_SOURCE_REPRODUCED_NOT_GAME_BUILD' or \
            previous_result['dolSha256'] != digest(game / 'sys/main.dol') or \
            previous_result['manifestSha256'] != digest(previous_manifest) or \
            previous_result['units'] != previous['units']:
        raise ValueError('FP guest stage does not match the verified Wii DATA')
    changed = {16, 18, 30, 32, 40, 44, 64}
    if expected['changedUnits'] != [f'output_{index}.cpp' for index in sorted(changed)]:
        raise ValueError('Late guest adapter manifest changed')

    dol = (game / 'sys/main.dol').read_bytes()
    destination.mkdir(mode=0o700)
    units = {}
    for index in range(75):
        name = f'output_{index}.cpp'
        source = fp_guest / name
        original = source.read_bytes()
        if record(original) != {key: previous['units'][name][key]
                for key in ('bytes', 'sha256')}:
            raise RuntimeError(f'FP guest source changed: {name}')
        data = adapt(original.decode(), dol, index).encode() if index in changed else original
        actual = record(data)
        if actual != expected['units'][name]:
            raise RuntimeError(f'Late guest adapter differs from verified Wii rev0: {name}')
        (destination / name).write_bytes(data)
        units[name] = actual

    report = {'result': 'OWNER_WII_SELECTED_LATE_GUEST_ADAPTERS_REPRODUCED_NOT_GAME_BUILD',
        'gameData': str(game), 'fpGuest': str(fp_guest),
        'dolSha256': digest(game / 'sys/main.dol'),
        'manifestSha256': digest(MANIFEST), 'units': units,
        'changedUnits': expected['changedUnits'],
        'limits': ['Generated guest source is private and must not enter a public package.',
            'PC boot and input hooks are native adapters; observer hooks are diagnostics.',
            'Only seven selected late guest units are restored; remaining guest/runtime changes remain.',
            'Only Wii US R5WEA4 revision 0 has been verified.']}
    (destination / 'recovery-result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--fp-guest', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    report = recover(args.game_data, args.fp_guest, args.destination)
    print(report['result'], len(report['units']), len(report['changedUnits']))


if __name__ == '__main__':
    main()

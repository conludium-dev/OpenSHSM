"""Reproduce Wii DMA guest lowering and CPU headers from owner-only inputs."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

from export_stock_wii_us_copy import verify_export
from recover_stock_optimized_guest import digest
from stock_locked_cache_patch import adapt_cpu_header, adapt_processor_header, lower_dma
from stock_quantization_patch import adapt_quantization
from verify_wii_us_copy import audit_copy


MANIFEST = Path(__file__).with_name('stock-dma-quantization-wii-us-r5wea4-rev0.json')


def record(data):
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def recover(game_data, stock_export, hid2_carry_guest, destination):
    game = Path(audit_copy(game_data)['source']).resolve(strict=True)
    stock_export = Path(stock_export).expanduser().resolve(strict=True)
    hid2_carry_guest = Path(hid2_carry_guest).expanduser().resolve(strict=True)
    destination = Path(destination).expanduser().absolute()
    if not destination.parent.is_dir():
        raise ValueError('Destination parent does not exist')
    destination = destination.parent.resolve(strict=True) / destination.name
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destination must be a fresh directory')
    if any(destination == source or source in destination.parents
            for source in (game, stock_export, hid2_carry_guest)):
        raise ValueError('Destination must be outside Wii DATA and prior stages')
    if shutil.disk_usage(destination.parent).free < 512 * 1024 * 1024:
        raise ValueError('Insufficient free space for recovered guest source')

    verify_export(stock_export)
    export_result = json.loads((stock_export.parent / 'export-result.json').read_text())
    previous_result = json.loads((hid2_carry_guest / 'recovery-result.json').read_text())
    expected = json.loads(MANIFEST.read_text())
    previous_manifest = Path(__file__).with_name(expected['source'])
    previous = json.loads(previous_manifest.read_text())
    dol_sha = digest(game / 'sys/main.dol')
    if expected['gameId'] != 'R5WEA4' or expected['revision'] != 0 or \
            set(expected['units']) != {f'output_{index}.cpp' for index in range(75)} or \
            export_result['result'] != 'OWNER_WII_US_R5WEA4_REV0_STOCK_SOURCE_EXPORTED_NOT_GAME_BUILD' or \
            Path(export_result['output']).resolve(strict=True) != stock_export or \
            export_result['dolSha256'] != dol_sha or \
            previous_result['result'] != 'OWNER_WII_HID2_CARRY_GUEST_SOURCE_REPRODUCED_NOT_GAME_BUILD' or \
            previous_result['dolSha256'] != dol_sha or \
            previous_result['manifestSha256'] != digest(previous_manifest) or \
            previous_result['units'] != previous['units']:
        raise ValueError('Source stages do not match the verified Wii DATA')

    dol = (game / 'sys/main.dol').read_bytes()
    destination.mkdir(mode=0o700)
    units = {}
    for index in range(75):
        name = f'output_{index}.cpp'
        source = hid2_carry_guest / name
        if record(source.read_bytes()) != {key: previous['units'][name][key]
                for key in ('bytes', 'sha256')}:
            raise RuntimeError(f'HID2/carry guest source changed: {name}')
        text, sites = lower_dma(source.read_text(), dol)
        data = text.encode()
        actual = {**record(data), 'dmaSites': len(sites)}
        if actual != expected['units'][name]:
            raise RuntimeError(f'DMA guest lowering differs from verified Wii rev0: {name}')
        (destination / name).write_bytes(data)
        units[name] = actual

    public = Path(__file__).resolve().parent
    cpu = (stock_export / 'nWiiRuntime/include/runtime/cpu_context.h').read_text()
    headers = {
        'include/runtime/cpu_context.h': adapt_quantization(adapt_cpu_header(cpu)),
        'processor_adapter.h': adapt_processor_header((public / 'processor_adapter.h').read_text()),
    }
    carry = (public / 'carry_adapter.h').read_text()
    marker = '#include "l2_adapter.h"'
    if carry.count(marker) != 1:
        raise RuntimeError('Unexpected carry adapter header')
    headers['carry_adapter.h'] = carry.replace(marker, '#include "runtime/cpu_context.h"')
    for name, text in headers.items():
        data = text.encode()
        if record(data) != expected['headers'][name]:
            raise RuntimeError(f'CPU header differs from verified Wii rev0: {name}')
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    report = {'result': 'OWNER_WII_DMA_QUANTIZATION_SOURCES_REPRODUCED_NOT_GAME_BUILD',
        'gameData': str(game), 'stockExport': str(stock_export),
        'hid2CarryGuest': str(hid2_carry_guest), 'dolSha256': dol_sha,
        'manifestSha256': digest(MANIFEST), 'units': units,
        'headers': expected['headers'],
        'limits': ['Generated guest source is private and must not enter a public package.',
            'This stage reproduces source and headers, not compiled objects or the full runtime.',
            'Only Wii US R5WEA4 revision 0 has been verified.']}
    (destination / 'recovery-result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--stock-export', type=Path, required=True)
    parser.add_argument('--hid2-carry-guest', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    report = recover(args.game_data, args.stock_export, args.hid2_carry_guest,
        args.destination)
    print(report['result'], len(report['units']), len(report['headers']))


if __name__ == '__main__':
    main()

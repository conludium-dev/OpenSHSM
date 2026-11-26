"""Reproduce the Wii guest FP guard source stage from owner-only inputs."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

from recover_stock_optimized_guest import digest
from stock_dcbz_lowering import lower_dcbz
from stock_fp_guard_lowering import lower as lower_fp_guard
from stock_idct_observation import adapt_idct
from verify_wii_us_copy import audit_copy


MANIFEST = Path(__file__).with_name('stock-fp-guard-wii-us-r5wea4-rev0.json')


def record(data):
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def recover(game_data, dma_quantization, destination):
    game = Path(audit_copy(game_data)['source']).resolve(strict=True)
    dma_quantization = Path(dma_quantization).expanduser().resolve(strict=True)
    destination = Path(destination).expanduser().absolute()
    if not destination.parent.is_dir():
        raise ValueError('Destination parent does not exist')
    destination = destination.parent.resolve(strict=True) / destination.name
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destination must be a fresh directory')
    if any(destination == source or source in destination.parents
            for source in (game, dma_quantization)):
        raise ValueError('Destination must be outside Wii DATA and prior guest stage')
    if shutil.disk_usage(destination.parent).free < 512 * 1024 * 1024:
        raise ValueError('Insufficient free space for recovered guest source')

    expected = json.loads(MANIFEST.read_text())
    previous_manifest = Path(__file__).with_name(expected['source'])
    previous = json.loads(previous_manifest.read_text())
    previous_result = json.loads((dma_quantization / 'recovery-result.json').read_text())
    if expected['gameId'] != 'R5WEA4' or expected['revision'] != 0 or \
            set(expected['units']) != {f'output_{index}.cpp' for index in range(75)} or \
            previous_result['result'] != 'OWNER_WII_DMA_QUANTIZATION_SOURCES_REPRODUCED_NOT_GAME_BUILD' or \
            previous_result['dolSha256'] != digest(game / 'sys/main.dol') or \
            previous_result['manifestSha256'] != digest(previous_manifest) or \
            previous_result['units'] != previous['units'] or \
            previous_result['headers'] != previous['headers']:
        raise ValueError('DMA/quantization stage does not match the verified Wii DATA')
    for name, row in previous['headers'].items():
        if record((dma_quantization / name).read_bytes()) != row:
            raise RuntimeError(f'CPU header changed: {name}')

    dol = (game / 'sys/main.dol').read_bytes()
    destination.mkdir(mode=0o700)
    units = {}
    idct_count = 0
    dcbz_count = 0
    for index in range(75):
        name = f'output_{index}.cpp'
        source = dma_quantization / name
        if record(source.read_bytes()) != {key: previous['units'][name][key]
                for key in ('bytes', 'sha256')}:
            raise RuntimeError(f'DMA guest source changed: {name}')
        text = source.read_text()
        if index == 37:
            text, idct = adapt_idct(text, dol)
            text, dcbz = lower_dcbz(text, dol)
            idct_count = len(idct)
            dcbz_count = len(dcbz)
        text, sites, fpscr = lower_fp_guard(text, dol, expected['classificationTables'])
        data = text.encode()
        actual = {**record(data), 'fpGuardSites': len(sites),
            'fpscrLowerings': len(fpscr)}
        if actual != expected['units'][name]:
            raise RuntimeError(f'FP guard guest lowering differs from verified Wii rev0: {name}')
        (destination / name).write_bytes(data)
        units[name] = actual
    if idct_count != expected['output37IdctSites'] or \
            dcbz_count != expected['output37DcbzSites']:
        raise RuntimeError('IDCT/dcbz site count differs from verified Wii rev0')

    report = {'result': 'OWNER_WII_FP_GUARD_GUEST_SOURCE_REPRODUCED_NOT_GAME_BUILD',
        'gameData': str(game), 'dmaQuantization': str(dma_quantization),
        'dolSha256': digest(game / 'sys/main.dol'),
        'manifestSha256': digest(MANIFEST), 'units': units,
        'output37IdctSites': idct_count, 'output37DcbzSites': dcbz_count,
        'limits': ['Generated guest source is private and must not enter a public package.',
            'FP opcode tables are Dolphin metadata for a host guard; Wii DOL bytes verify each patched site.',
            'Runtime FP guard adapter, compilation and later guest stages remain.',
            'Only Wii US R5WEA4 revision 0 has been verified.']}
    (destination / 'recovery-result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--dma-quantization', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    report = recover(args.game_data, args.dma_quantization, args.destination)
    print(report['result'], len(report['units']),
        sum(row['fpGuardSites'] for row in report['units'].values()))


if __name__ == '__main__':
    main()

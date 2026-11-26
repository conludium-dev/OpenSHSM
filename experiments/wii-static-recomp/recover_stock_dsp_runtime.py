"""Reproduce the active DSP source through verified ADMA and AXWii PC stages."""
from pathlib import Path
import argparse
import json
import shutil

from export_stock_wii_us_copy import digest
from recover_stock_late_adapter_guest import record
from stock_adma_accounting_patch import counted_dsp, counted_output
from stock_axwii_device_patch import adapt as axwii
from stock_dsp_capture_patch import adapt as capture
from verify_wii_us_copy import audit_copy


MANIFEST = Path(__file__).with_name('stock-dsp-runtime-wii-us-r5wea4-rev0.json')
SOURCE = 'src/hw/hw_dsp.cpp'
STAGES = (
    ('supply', '#include "stock_dsp_supply.h"\n'),
    ('chunks', '#include "stock_adma_cursor.h"\n#include "stock_adma_output.h"\n'),
    ('deadline', ''),
)


def apply_patches(text, patches):
    for before, after in patches:
        if text.count(before) != 1:
            raise ValueError('DSP stage patch site differs')
        text = text.replace(before, after, 1)
    return text


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
    source = stock_export / 'nWiiRuntime' / SOURCE
    data = source.read_bytes()
    if record(data) != stock_manifest['runtime'][SOURCE]:
        raise ValueError('Stock DSP source changed')
    text = data.decode()
    for name, prefix in STAGES[:2]:
        text = prefix + apply_patches(text, expected['patches'][name])
        if record(text.encode()) != expected['stages'][name]:
            raise RuntimeError(f'DSP {name} stage differs')
    text = counted_dsp(text)
    if record(text.encode()) != expected['stages']['accounting']:
        raise RuntimeError('DSP accounting stage differs')
    text = apply_patches(text, expected['patches']['deadline'])
    if record(text.encode()) != expected['stages']['deadline']:
        raise RuntimeError('DSP deadline stage differs')
    text = axwii(capture(text))
    public = Path(__file__).resolve().parent
    generated = {
        SOURCE: text.encode(),
        'stock_adma_output.h': counted_output((public / 'stock_adma_output.h').read_text()).encode(),
    }
    if {name: record(data) for name, data in generated.items()} != expected['outputs']:
        raise RuntimeError('Active DSP runtime differs from verified Wii rev0')
    from stock_adma_stereo_patch import adapt as stereo
    generated[SOURCE] = stereo(generated[SOURCE].decode()).encode()
    if record(generated[SOURCE]) != expected['stereoOutput']:
        raise RuntimeError('ADMA stereo stage differs')
    from stock_adma_reporting_patch import dsp as reporting
    generated[SOURCE] = reporting(generated[SOURCE].decode()).encode()
    if record(generated[SOURCE]) != expected['reportingOutput']:
        raise RuntimeError('ADMA reporting stage differs')
    from stock_adma_reporting_patch import jobs as job_accounting
    generated[SOURCE] = job_accounting(generated[SOURCE].decode()).encode()
    if record(generated[SOURCE]) != expected['jobAccountingOutput']:
        raise RuntimeError('AX job accounting stage differs')
    from stock_fmod_event_accounting_patch import dsp as event_accounting
    generated[SOURCE] = event_accounting(generated[SOURCE].decode()).encode()
    if record(generated[SOURCE]) != expected['fmodAccountingOutput']:
        raise RuntimeError('FMOD result accounting stage differs')
    destination.mkdir(mode=0o700)
    for name, data in generated.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    report = {'result': 'OWNER_WII_ACTIVE_DSP_RUNTIME_SOURCE_REPRODUCED_NOT_GAME_AUDIO',
        'dolSha256': digest(dol_path), 'manifestSha256': digest(MANIFEST),
        'outputs': {name: record(data) for name, data in generated.items()},
        'limits': ['ADMA/DSP/AXWii mixer stages are PC adaptations.',
            'Audible quality and full game acceptance remain unverified.',
            'Only Wii US R5WEA4 revision 0 has been verified.']}
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

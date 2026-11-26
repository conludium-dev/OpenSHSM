"""Reproduce active AI, IOS kernel and platform runtime sources from own Wii."""
from pathlib import Path
import argparse
import json
import shutil

from export_stock_wii_us_copy import digest
from recover_stock_late_adapter_guest import record
from stock_audio_patch import adapt_audio
from stock_fs_commands_patch import adapt_kernel
from stock_ios_negative_fd_patch import adapt as adapt_platform_ios
from verify_wii_us_copy import audit_copy


MANIFEST = Path(__file__).with_name('stock-core-runtime-wii-us-r5wea4-rev0.json')
SOURCES = ('src/hw/hw_ai.cpp', 'src/hle/ios_kernel.cpp', 'src/platform/wii_platform.cpp')


def adapt(name, text):
    if name == 'src/hw/hw_ai.cpp':
        text = adapt_audio(text)
        marker = 'static uint32_t ai_cr = 0;'
        if text.count(marker) != 1:
            raise ValueError('AI sample-rate patch site differs')
        return text.replace(marker, marker + '\n'
            'uint32_t ai_dma_sample_rate() { return (ai_cr & 0x40) ? 32000 : 48000; }', 1)
    if name == 'src/hle/ios_kernel.cpp':
        return adapt_kernel(text)
    if name == 'src/platform/wii_platform.cpp':
        return adapt_platform_ios(text)
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
            stock_result['result'] != 'OWNER_WII_US_R5WEA4_REV0_STOCK_SOURCE_EXPORTED_NOT_GAME_BUILD' or \
            stock_result['dolSha256'] != digest(dol_path) or \
            set(expected['outputs']) != set(SOURCES):
        raise ValueError('Stock runtime does not match verified Wii US rev0 DATA')
    generated = {}
    for name in SOURCES:
        original = (stock_export / 'nWiiRuntime' / name).read_bytes()
        if record(original) != stock_manifest['runtime'][name]:
            raise ValueError(f'Stock runtime source changed: {name}')
        generated[name] = adapt(name, original.decode()).encode()
    if {name: record(data) for name, data in generated.items()} != expected['outputs']:
        raise RuntimeError('Active core runtime differs from verified Wii rev0')
    destination.mkdir(mode=0o700)
    for name, data in generated.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    report = {'result': 'OWNER_WII_ACTIVE_CORE_RUNTIME_SOURCES_REPRODUCED_NOT_RUNTIME_BUILD',
        'dolSha256': digest(dol_path), 'manifestSha256': digest(MANIFEST),
        'outputs': {name: record(data) for name, data in generated.items()},
        'limits': ['AI timing and /dev/fs routing are PC runtime adapters.',
            'Audio quality, IOS behavior and full game acceptance remain.',
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

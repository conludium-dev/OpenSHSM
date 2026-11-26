"""Reproduce the active ES and persistent FS sources from own Wii runtime."""
from pathlib import Path
import argparse
import json
import shutil

from export_stock_wii_us_copy import digest
from recover_stock_late_adapter_guest import record
from stock_fs_commands_patch import adapt as fs_commands
from stock_nand_hierarchy_patch import adapt_es, adapt_fs
from stock_sysconf_patch import adapt as sysconf
from stock_vnand_persistence_patch import adapt_rename, adapt_source
from verify_wii_us_copy import audit_copy


MANIFEST = Path(__file__).with_name('stock-nand-runtime-wii-us-r5wea4-rev0.json')
STOCK_SOURCES = ('src/hle/devices/es_device.cpp', 'src/hle/devices/fs_device.cpp')


def rename_commands(text):
    marker = '    int32_t ioctl(CPUContext& ctx, const IpcRequest& req) override {\n'
    if text.count(marker) != 1:
        raise ValueError('FS ioctl site differs')
    text = text.replace(marker, '    #include "stock_fs_rename.inc"\n\n' + marker, 1)
    marker = '        const uint32_t out = fs_virtual(req.out_buf), in = fs_virtual(req.in_buf);\n'
    if text.count(marker) != 1:
        raise ValueError('FS rename routing site differs')
    return text.replace(marker, marker +
        '        if (req.ioctl_cmd == 8) {\n            return rename_node(ctx, req);\n        }\n', 1)


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
    stock = {}
    for name in STOCK_SOURCES:
        data = (stock_export / 'nWiiRuntime' / name).read_bytes()
        if record(data) != stock_manifest['runtime'][name]:
            raise ValueError(f'Stock runtime source changed: {name}')
        stock[name] = data.decode()

    es = adapt_es(stock[STOCK_SOURCES[0]])
    fs = adapt_fs(fs_commands(stock[STOCK_SOURCES[1]]))
    marker = '#include "stock_fs_commands.inc"'
    if fs.count(marker) != 1:
        raise ValueError('FS command include differs')
    fs = adapt_source(sysconf(fs.replace(marker, '#include "stock_fs_rename_commands.inc"', 1)))
    public = Path(__file__).resolve().parent
    generated = {
        STOCK_SOURCES[0]: es.encode(),
        STOCK_SOURCES[1]: fs.encode(),
        'stock_fs_rename_commands.inc': rename_commands(
            (public / 'stock_fs_commands.inc').read_text()).encode(),
        'stock_fs_rename.inc': adapt_rename((public / 'stock_fs_rename.inc').read_text()).encode(),
    }
    if set(generated) != set(expected['outputs']) or \
            {name: record(data) for name, data in generated.items()} != expected['outputs']:
        raise RuntimeError('Active NAND runtime differs from verified Wii rev0')
    destination.mkdir(mode=0o700)
    for name, data in generated.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    report = {'result': 'OWNER_WII_ACTIVE_NAND_RUNTIME_SOURCES_REPRODUCED_NOT_GAME_BUILD',
        'dolSha256': digest(dol_path), 'manifestSha256': digest(MANIFEST),
        'outputs': {name: record(data) for name, data in generated.items()},
        'limits': ['ES hierarchy, SYSCONF and durable VNAND are PC adapters.',
            'Only Wii US R5WEA4 revision 0 has been verified.',
            'Console NAND behavior and full game acceptance remain unverified.']}
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

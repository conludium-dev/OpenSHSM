"""Reproduce the current IPC reply adapter from a verified own-Wii export."""
from pathlib import Path
import argparse
import ast
import json
import shutil

from export_stock_wii_us_copy import digest
from recover_stock_late_adapter_guest import record
from verify_wii_us_copy import audit_copy


MANIFEST = Path(__file__).with_name('stock-ipc-runtime-wii-us-r5wea4-rev0.json')
SOURCE = 'src/hw/hw_ipc.cpp'


def queue_replacements():
    builder = ast.parse(Path(__file__).with_name('build_stock_ipc_queue.py').read_text())
    assignments = [node for node in builder.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'replacements'
            for target in node.targets)]
    if len(assignments) != 1:
        raise ValueError('Existing IPC queue recipe differs')
    pairs = ast.literal_eval(assignments[0].value)
    if len(pairs) != 8 or any(len(pair) != 2 for pair in pairs):
        raise ValueError('Existing IPC queue patch count differs')
    return pairs


def adapt(text):
    for before, after in queue_replacements():
        if text.count(before) != 1:
            raise ValueError('Stock IPC queue patch site differs')
        text = text.replace(before, after, 1)
    marker = 'static void complete_reply(uint32_t address) {\n'
    if text.count(marker) != 1:
        raise ValueError('IPC reply publication site differs')
    return '#include "stock_ipc_reply.h"\n#include <stdexcept>\n' + text.replace(marker,
        marker + '    if (!g_mmu || !openshsm::experiment::prepare_ipc_reply(*g_mmu, address)) {\n'
        '        throw std::runtime_error("Invalid IPC completion header/backing");\n'
        '    }\n', 1)


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
    source = stock_export / 'nWiiRuntime' / SOURCE
    dol_path = game / 'sys/main.dol'
    if expected['gameId'] != 'R5WEA4' or expected['revision'] != 0 or \
            stock_result['result'] != 'OWNER_WII_US_R5WEA4_REV0_STOCK_SOURCE_EXPORTED_NOT_GAME_BUILD' or \
            stock_result['dolSha256'] != digest(dol_path) or \
            record(source.read_bytes()) != stock_manifest['runtime'][SOURCE]:
        raise ValueError('Stock IPC source is not from verified Wii US rev0 export')
    data = adapt(source.read_text()).encode()
    if record(data) != expected['ipc']:
        raise RuntimeError('Current IPC source differs from verified Wii rev0')
    destination.mkdir(mode=0o700)
    (destination / 'hw_ipc.cpp').write_bytes(data)
    report = {'result': 'OWNER_WII_ACTIVE_IPC_SOURCE_REPRODUCED_NOT_RUNTIME_BUILD',
        'dolSha256': digest(dol_path), 'manifestSha256': digest(MANIFEST),
        'stockSourceSha256': digest(source), 'ipc': record(data),
        'limits': ['IPC queue and reply-header repair are PC runtime adapters.',
            'Complete IOS behavior and full game acceptance remain.',
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

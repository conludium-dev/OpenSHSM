"""Reproduce the active PowerPC fallback source from a verified own-Wii export."""
from pathlib import Path
import argparse
import json
import shutil

from export_stock_wii_us_copy import digest
from recover_stock_late_adapter_guest import record
from stock_fp_unavailable_patch import adapt_interpreter as fp_guard
from stock_interpreter_addze import adapt as addze
from stock_interpreter_lhaux import adapt as halfword, check_dol
from stock_interpreter_reached_ops import adapt as reached
from stock_locked_cache_patch import adapt_interpreter as dma
from stock_scan_consumption import adapt_interpreter as scan
from verify_wii_us_copy import audit_copy


MANIFEST = Path(__file__).with_name('stock-interpreter-runtime-wii-us-r5wea4-rev0.json')


def adapt(text):
    patches = (
        ('else if (spr == 27) ctx.gpr[rD] = ctx.srr1;',
            'else if (spr == 27) ctx.gpr[rD] = ctx.srr1;\n'
            '            else if (spr == 920) ctx.gpr[rD] = experiment_read_hid2(ctx);'),
        ('else if (spr == 27) ctx.srr1 = ctx.gpr[rD];',
            'else if (spr == 27) ctx.srr1 = ctx.gpr[rD];\n'
            '            else if (spr == 920) experiment_write_hid2(ctx, ctx.gpr[rD]);'))
    for before, after in patches:
        if text.count(before) != 1:
            raise ValueError('Stock processor interpreter site differs')
        text = text.replace(before, after, 1)
    text = dma('#include "processor_adapter.h"\n' + text)
    text = fp_guard(text, complete=True)
    marker = '#include "stock_fp_unavailable.h"\n'
    if text.count(marker) != 1:
        raise ValueError('FP guard include differs')
    text = text.replace(marker, marker + '#include "fpscr_adapter.h"\n', 1)
    before = 'case 38: case 70: case 134: case 711: break;'
    if text.count(before) != 1:
        raise ValueError('FPSCR opcode site differs')
    text = text.replace(before, 'case 711: experiment_mtfsf(ctx, insn); break;\n'
        '        case 38: case 70: case 134: break;', 1)
    return halfword(reached(addze(scan(text))))


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
    source = stock_export / 'nWiiRuntime/src/hle/interpreter.cpp'
    dol_path = game / 'sys/main.dol'
    if expected['gameId'] != 'R5WEA4' or expected['revision'] != 0 or \
            stock_result['result'] != 'OWNER_WII_US_R5WEA4_REV0_STOCK_SOURCE_EXPORTED_NOT_GAME_BUILD' or \
            stock_result['dolSha256'] != digest(dol_path) or \
            record(source.read_bytes()) != stock_manifest['runtime']['src/hle/interpreter.cpp'] or \
            expected['source'] != 'stock-export-wii-us-r5wea4-rev0.json':
        raise ValueError('Stock interpreter is not from verified Wii US rev0 export')
    check_dol(dol_path.read_bytes())
    data = adapt(source.read_text()).encode()
    if record(data) != expected['interpreter']:
        raise RuntimeError('Active interpreter source differs from verified Wii rev0')
    destination.mkdir(mode=0o700)
    (destination / 'interpreter.cpp').write_bytes(data)
    report = {'result': 'OWNER_WII_ACTIVE_INTERPRETER_SOURCE_REPRODUCED_NOT_RUNTIME_BUILD',
        'dolSha256': digest(dol_path), 'manifestSha256': digest(MANIFEST),
        'stockSourceSha256': digest(source), 'interpreter': record(data),
        'limits': ['Current fallback and hardware shims include PC adapters.',
            'Guest exception behavior, full runtime archive and game acceptance remain.',
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

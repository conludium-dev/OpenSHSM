"""Reproduce the current ADMA scheduler source from a verified own-Wii export."""
from pathlib import Path
import argparse
import json
import shutil

from export_stock_wii_us_copy import digest
from recover_stock_late_adapter_guest import record
from verify_wii_us_copy import audit_copy


MANIFEST = Path(__file__).with_name('stock-scheduler-runtime-wii-us-r5wea4-rev0.json')
SOURCE = 'src/core/event_scheduler.cpp'
HEADER = 'include/runtime/event_scheduler.h'


def adapt(source, header):
    source_marker = 'EventScheduler::EventId EventScheduler::schedule_after('
    if source.count(source_marker) != 1:
        raise ValueError('Stock scheduler source site differs')
    addition = '''EventScheduler::EventId EventScheduler::schedule_at(uint64_t due, Callback cb) {
    EventId id = m_next_id++;
    push({due, id, 0, std::move(cb)});
    return id;
}

'''
    header_marker = '    EventId schedule_after(uint64_t delay, Callback cb);'
    if header.count(header_marker) != 1:
        raise ValueError('Stock scheduler header site differs')
    header_addition = header_marker + '\n\n    // Preserve chronological ordering of overdue device events.\n' \
        '    EventId schedule_at(uint64_t due, Callback cb);'
    return source.replace(source_marker, addition + source_marker, 1), \
        header.replace(header_marker, header_addition, 1)


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
            stock_result['dolSha256'] != digest(dol_path):
        raise ValueError('Stock export does not match verified Wii US rev0 DATA')
    originals = {SOURCE: (stock_export / 'nWiiRuntime' / SOURCE).read_bytes(),
        HEADER: (stock_export / 'nWiiRuntime' / HEADER).read_bytes()}
    for name, data in originals.items():
        if record(data) != stock_manifest['runtime'][name]:
            raise ValueError(f'Stock scheduler input changed: {name}')
    source, header = adapt(originals[SOURCE].decode(), originals[HEADER].decode())
    generated = {SOURCE: source.encode(), HEADER: header.encode()}
    if {name: record(data) for name, data in generated.items()} != expected['outputs']:
        raise RuntimeError('ADMA scheduler differs from verified Wii rev0')
    destination.mkdir(mode=0o700)
    for name, data in generated.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    report = {'result': 'OWNER_WII_ACTIVE_SCHEDULER_SOURCE_REPRODUCED_NOT_RUNTIME_BUILD',
        'dolSha256': digest(dol_path), 'manifestSha256': digest(MANIFEST),
        'outputs': {name: record(data) for name, data in generated.items()},
        'limits': ['ADMA schedule_at is a PC runtime adapter.',
            'Chronological scheduling and full game timing acceptance remain.',
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

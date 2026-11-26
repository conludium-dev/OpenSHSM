"""Reproduce the original Wii scan wrapper and its existing PC observers."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

from export_stock_wii_us_copy import digest
from recover_stock_late_adapter_guest import record
from stock_scan_restore import restore_guest
from stock_scan_observation import adapt as observe_scan
from stock_scan_consumption import IMPLEMENTATION
from stock_numeric_reader import adapt as observe_numeric
from verify_wii_us_copy import audit_copy


MANIFEST = Path(__file__).with_name('stock-scan-guest-wii-us-r5wea4-rev0.json')
SCAN_FUNCTION_SHA256 = '025545ecbf9aeb7204e7ad9af52f7575595e6977f7a256b7023d6b38de94401b'


def recover(game_data, paired_guest, mass_guest, tables_report, destination):
    game = Path(audit_copy(game_data)['source']).resolve(strict=True)
    paired_guest = Path(paired_guest).expanduser().resolve(strict=True)
    mass_guest = Path(mass_guest).expanduser().resolve(strict=True)
    tables_report = Path(tables_report).expanduser().resolve(strict=True) if tables_report else None
    destination = Path(destination).expanduser().absolute()
    if not destination.parent.is_dir():
        raise ValueError('Destination parent does not exist')
    destination = destination.parent.resolve(strict=True) / destination.name
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destination must be a fresh directory')
    if any(destination == source or source in destination.parents
            for source in (game, paired_guest, mass_guest.parent)):
        raise ValueError('Destination must be outside inputs')
    if shutil.disk_usage(destination.parent).free < 512 * 1024 * 1024:
        raise ValueError('Insufficient free space')

    expected = json.loads(MANIFEST.read_text())
    previous_manifest = Path(__file__).with_name(expected['source'])
    previous = json.loads(previous_manifest.read_text())
    previous_result = json.loads((paired_guest / 'recovery-result.json').read_text())
    dol_path = game / 'sys/main.dol'
    if expected['gameId'] != 'R5WEA4' or expected['revision'] != 0 or \
            previous_result['result'] != 'OWNER_WII_PAIRED_GUEST_SOURCES_REPRODUCED_NOT_GAME_BUILD' or \
            previous_result['dolSha256'] != digest(dol_path) or \
            previous_result['manifestSha256'] != digest(previous_manifest) or \
            previous_result['units'] != previous['units']:
        raise ValueError('Paired guest stage does not match verified Wii DATA')
    mass = mass_guest.read_text()
    start = mass.index('void func_8019D434(CPUContext& ctx) {')
    end = mass.find('\nvoid func_', start + 1)
    body = mass[start:end if end >= 0 else len(mass)].rstrip('\n') + '\n'
    if digest(mass_guest) != expected['massGuestSha256'] and \
            hashlib.sha256(body.encode()).hexdigest() != SCAN_FUNCTION_SHA256:
        raise ValueError('Generated Wii inputs differ from verified scan restoration')

    dol = dol_path.read_bytes()
    tables = json.loads(Path(__file__).with_name('stock-fp-guard-wii-us-r5wea4-rev0.json').read_text())['classificationTables']
    if tables_report and (digest(tables_report) != expected['tablesReportSha256'] or
            json.loads(tables_report.read_text())['tables'] != tables):
        raise ValueError('Private FP tables report differs from public verified classification')
    destination.mkdir(mode=0o700)
    units = {}
    words = []
    for index in range(75):
        name = f'output_{index}.cpp'
        original = (paired_guest / name).read_bytes()
        if record(original) != {key: previous['units'][name][key] for key in ('bytes', 'sha256')}:
            raise RuntimeError(f'Paired guest changed: {name}')
        data = original
        if index == 31:
            text, words = restore_guest(original.decode(), mass, dol, tables)
            text = observe_scan(text, dol) + IMPLEMENTATION
            data = observe_numeric(text, dol, flight=True).encode()
        actual = record(data)
        if actual != expected['units'][name]:
            raise RuntimeError(f'Scan guest differs from verified Wii rev0: {name}')
        (destination / name).write_bytes(data)
        units[name] = actual
    if len(words) != expected['originalWords']:
        raise RuntimeError('Original scan wrapper word count changed')
    report = {'result': 'OWNER_WII_SCAN_GUEST_SOURCES_REPRODUCED_NOT_GAME_BUILD',
        'gameData': str(game), 'pairedGuest': str(paired_guest),
        'dolSha256': digest(dol_path), 'manifestSha256': digest(MANIFEST),
        'units': units, 'originalWords': len(words),
        'limits': ['Generated guest source is private and must not enter a public package.',
            'Observer hooks are PC adapters; scan wrapper words are Wii DOL verified.',
            'Runtime, compilation, linking and full game acceptance remain.',
            'Only Wii US R5WEA4 revision 0 has been verified.']}
    (destination / 'recovery-result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--paired-guest', type=Path, required=True)
    parser.add_argument('--mass-guest', type=Path, required=True)
    parser.add_argument('--tables-report', type=Path)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    report = recover(args.game_data, args.paired_guest, args.mass_guest,
        args.tables_report, args.destination)
    print(report['result'], len(report['units']), report['originalWords'])


if __name__ == '__main__':
    main()

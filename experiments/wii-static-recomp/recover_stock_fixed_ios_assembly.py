"""Restore two Wii functions misidentified as IOS HLE in the assembled sources."""
from pathlib import Path
import argparse
import json
import shutil

from export_stock_wii_us_copy import FIXED_SIGNATURE_MANIFEST, digest
from recover_stock_late_adapter_guest import record
from recover_stock_host_inputs import bounds_source
from stock_fixed_ios_signature_patch import restored_assembly
from verify_wii_us_copy import audit_copy


MANIFEST = Path(__file__).with_name('stock-fixed-ios-assembly-wii-us-r5wea4-rev0.json')


def recover(game_data, assembly, stock_export, destination):
    game = Path(audit_copy(game_data)['source']).resolve(strict=True)
    assembly = Path(assembly).resolve(strict=True)
    stock_export = Path(stock_export).resolve(strict=True)
    destination = Path(destination).expanduser().absolute()
    if not destination.parent.is_dir():
        raise ValueError('Destination parent does not exist')
    destination = destination.parent.resolve(strict=True) / destination.name
    if destination.exists() or destination.is_symlink() or \
            any(destination == source or source in destination.parents
                for source in (game, assembly, stock_export)):
        raise ValueError('Destination must be fresh and outside inputs')
    if shutil.disk_usage(destination.parent).free < 512 * 1024 * 1024:
        raise ValueError('Insufficient free space')

    dol_sha = digest(game / 'sys/main.dol')
    expected = json.loads(MANIFEST.read_text())
    fixed_expected = json.loads(FIXED_SIGNATURE_MANIFEST.read_text())
    stock_report = json.loads((stock_export.parent / 'export-result.json').read_text())
    corrected = stock_report.get('correctedSignatures')
    if expected['gameId'] != 'R5WEA4' or expected['revision'] != 0 or \
            expected['source'] != FIXED_SIGNATURE_MANIFEST.name or \
            stock_report['dolSha256'] != dol_sha or not corrected or \
            corrected['manifestSha256'] != digest(FIXED_SIGNATURE_MANIFEST) or \
            set(corrected['sources']) != set(fixed_expected['changedFiles']):
        raise ValueError('Corrected Wii stock export is required')
    raw = {}
    for name, fingerprint in fixed_expected['changedFiles'].items():
        row = corrected['sources'][name]
        path = (stock_export.parent / 'corrected-signatures' / name).resolve(strict=True)
        if Path(row['path']).resolve(strict=True) != path or \
                path.stat().st_size != fingerprint['bytes'] or \
                digest(path) != fingerprint['sha256'] or \
                {key: row[key] for key in ('bytes', 'sha256')} != fingerprint:
            raise ValueError(f'Corrected guest source differs: {name}')
        raw[name] = path.read_text()

    report_path = assembly / 'owner-source-assembly-result.json'
    report = json.loads(report_path.read_text())
    if report['result'] != 'OWNER_WII_SOURCES_ASSEMBLED_NOT_COMPILED' or \
            report['dolSha256'] != dol_sha or \
            (report['guestSources'], report['runtimeSources'], report['hostSources']) != (75, 45, 4):
        raise ValueError('Assembled sources differ')
    for name, fingerprint in report['overlays'].items():
        if record((assembly / name).read_bytes()) != fingerprint:
            raise ValueError(f'Assembled overlay changed: {name}')
    targets = ('output_41.cpp', 'output_52.cpp')
    guest = {name: (assembly / name).read_text() for name in targets}
    patched, fixed, details = restored_assembly(guest,
        (assembly / 'fixed.cpp').read_text(), raw)
    patched['fixed.cpp'] = fixed
    patched['bounds.cpp'] = bounds_source(fixed,
        expected['boundsRecords'], expected['boundsRanges'])
    if set(patched) != set(expected['changedFiles']):
        raise RuntimeError('Corrected assembled file set differs')
    for name, text in patched.items():
        if record(text.encode()) != expected['changedFiles'][name]:
            raise RuntimeError(f'Corrected assembled source differs: {name}')

    shutil.copytree(assembly, destination)
    for name, text in patched.items():
        (destination / name).write_text(text)
        report['overlays'][name] = record(text.encode())
    report['fixedIosSignatures'] = {'manifestSha256': digest(MANIFEST),
        'sourceManifestSha256': digest(FIXED_SIGNATURE_MANIFEST),
        'details': details}
    (destination / report_path.name).write_text(json.dumps(report, indent=2) + '\n')
    result = {'result': 'OWNER_WII_FALSE_IOS_SIGNATURES_RESTORED_NOT_COMPILED',
        'dolSha256': dol_sha, 'sourceAssemblySha256': digest(report_path),
        'assemblyResultSha256': digest(destination / report_path.name),
        'changedFiles': expected['changedFiles'], 'details': details,
        'limits': ['Two exact Wii US rev0 functions, host dispatch and its derived bounds indices changed.',
            'Compilation and game behavior require separate verification.']}
    (destination / 'fixed-ios-result.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--assembly', type=Path, required=True)
    parser.add_argument('--stock-export', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    print(recover(args.game_data, args.assembly, args.stock_export,
        args.destination)['result'])


if __name__ == '__main__':
    main()

"""Export the stock recompilation from a verified owner-supplied Wii DATA tree."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess

from verify_wii_us_copy import audit_copy


STOCK_MANIFEST = Path(__file__).with_name('stock-export-wii-us-r5wea4-rev0.json')
FIXED_SIGNATURE_MANIFEST = Path(__file__).with_name(
    'stock-fixed-ios-signature-export-wii-us-r5wea4-rev0.json')


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def apple_double_sidecar(path):
    if not path.name.startswith('._') or not path.with_name(path.name[2:]).exists():
        return False
    with path.open('rb') as stream:
        return stream.read(8) == b'\x00\x05\x16\x07\x00\x02\x00\x00'


def verify_export(output):
    expected = [f'output_{index}.cpp' for index in range(75)] + [
        'main_output.cpp', 'functions.h', 'CMakeLists.txt']
    manifest = json.loads(STOCK_MANIFEST.read_text())
    if manifest['gameId'] != 'R5WEA4' or manifest['revision'] != 0 or \
            set(manifest['guest']) != set(expected):
        raise RuntimeError('Unexpected stock export manifest')
    actual = {path.name for path in output.glob('output_*.cpp')}
    if actual != set(expected[:75]) or any(not (output / name).is_file()
            for name in expected):
        raise RuntimeError(f'Unexpected Wii US rev0 export; inspect {output}')
    files = {name: {'bytes': (output / name).stat().st_size,
        'sha256': digest(output / name)} for name in expected}
    if files != manifest['guest']:
        raise RuntimeError(f'Stock guest output differs from Wii US rev0 manifest: {output}')
    runtime_root = output / 'nWiiRuntime'
    runtime_files = {str(path.relative_to(runtime_root)):
        {'bytes': path.stat().st_size, 'sha256': digest(path)}
        for path in runtime_root.rglob('*') if path.is_file() and not apple_double_sidecar(path)}
    if runtime_files != manifest['runtime']:
        raise RuntimeError(f'Upstream runtime output differs from pinned manifest: {output}')
    return manifest, files, runtime_files


def require_corrected_signatures(result_path):
    report = json.loads(Path(result_path).read_text())
    corrected = report.get('correctedSignatures') if isinstance(report, dict) else None
    expected = json.loads(FIXED_SIGNATURE_MANIFEST.read_text())
    if not isinstance(corrected, dict) or \
            corrected.get('manifestSha256') != digest(FIXED_SIGNATURE_MANIFEST) or \
            not isinstance(corrected.get('sources'), dict) or \
            set(corrected['sources']) != set(expected['changedFiles']):
        raise ValueError('Owner build requires the corrected IOS signature export. '
            'Prepare pinned sources with prepare_stock_nwii_source.py and rebuild nwiirecomp; '
            'an older executable can still contain the false IOS_IoctlvAsync signature.')


def normalize_corrected_signatures(output, destination):
    from stock_fixed_ios_signature_patch import normalized_stock

    baseline = json.loads(STOCK_MANIFEST.read_text())
    fixed = json.loads(FIXED_SIGNATURE_MANIFEST.read_text())
    if fixed['gameId'] != 'R5WEA4' or fixed['revision'] != 0 or \
            fixed['source'] != STOCK_MANIFEST.name:
        raise RuntimeError('Corrected signature manifest differs')
    names = set(fixed['changedFiles'])
    current = {name: {'bytes': (output / name).stat().st_size,
        'sha256': digest(output / name)} for name in baseline['guest']}
    if current == baseline['guest']:
        return None
    if {name: current[name] for name in names} != fixed['changedFiles'] or \
            any(current[name] != fingerprint for name, fingerprint in baseline['guest'].items()
                if name not in names):
        raise RuntimeError(f'Stock guest output differs from both verified manifests: {output}')
    raw = {name: (output / name).read_text() for name in names}
    normalized = normalized_stock(raw)
    for name in names:
        data = normalized[name].encode()
        if {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()} != baseline['guest'][name]:
            raise RuntimeError(f'Normalized stock source differs: {name}')
    corrected_dir = destination / 'corrected-signatures'
    corrected_dir.mkdir(mode=0o700)
    for name in names:
        shutil.copy2(output / name, corrected_dir / name)
        (output / name).write_bytes(normalized[name].encode())
    return {'manifestSha256': digest(FIXED_SIGNATURE_MANIFEST),
        'sources': {name: {'path': str(corrected_dir / name), **fixed['changedFiles'][name]}
            for name in sorted(names)}}


def export(game_data, recompiler, runtime_source, destination):
    game = Path(audit_copy(game_data)['source']).resolve(strict=True)
    recompiler = Path(recompiler).expanduser().resolve(strict=True)
    runtime_source = Path(runtime_source).expanduser().resolve(strict=True)
    destination = Path(destination).expanduser().absolute()
    if not recompiler.is_file() or not os.access(recompiler, os.X_OK):
        raise ValueError('nwiirecomp must be an executable file')
    if not (runtime_source / 'include/runtime/cpu_context.h').is_file():
        raise ValueError('Expected the upstream nWiiRuntime source directory')
    if not destination.parent.is_dir():
        raise ValueError('Destination parent does not exist')
    destination = destination.parent.resolve(strict=True) / destination.name
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destination must be a fresh directory')
    if destination == game or game in destination.parents:
        raise ValueError('Destination must be outside Wii DATA')
    if shutil.disk_usage(destination.parent).free < 512 * 1024 * 1024:
        raise ValueError('Insufficient free space for stock source export')

    destination.mkdir(mode=0o700)
    output = destination / 'export'
    config = destination / 'recompile.toml'
    fields = {
        'project_name': 'OpenSHSMStockBaseline',
        'input_game_dir': str(game),
        'output_dir': str(output),
        'runtime_source_dir': str(runtime_source),
    }
    config.write_text(''.join(f'{name} = {json.dumps(value)}\n'
        for name, value in fields.items()) +
        'split_output = true\ninstructions_per_file = 20000\n')
    log = destination / 'export.log'
    with log.open('wb') as stream:
        result = subprocess.run([str(recompiler), str(config)], cwd=destination,
            stdout=stream, stderr=subprocess.STDOUT, timeout=900)
    if result.returncode:
        raise RuntimeError(f'nwiirecomp exited {result.returncode}; inspect {log}')

    corrected_signatures = normalize_corrected_signatures(output, destination)
    manifest, files, runtime_files = verify_export(output)
    report = {
        'result': 'OWNER_WII_US_R5WEA4_REV0_STOCK_SOURCE_EXPORTED_NOT_GAME_BUILD',
        'gameData': str(game),
        'dolSha256': digest(game / 'sys/main.dol'),
        'recompiler': str(recompiler),
        'recompilerSha256': digest(recompiler),
        'runtimeSource': str(runtime_source),
        'configSha256': digest(config),
        'manifestSha256': digest(STOCK_MANIFEST),
        'upstreamRevision': manifest['upstreamRevision'],
        'output': str(output),
        'files': files,
        'runtimeFiles': runtime_files,
        'correctedSignatures': corrected_signatures,
        'limits': [
            'Generated guest source is private and must not be included in a public package.',
            'This stock export does not apply OpenSHSM patches or build a playable executable.',
            'Only Wii US R5WEA4 revision 0 has been verified.',
        ],
    }
    (destination / 'export-result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--recompiler', type=Path, required=True)
    parser.add_argument('--runtime-source', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = export(args.game_data, args.recompiler, args.runtime_source,
            args.destination)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f'{error}\n')
    print(result['result'], result['output'], len(result['files']))


if __name__ == '__main__':
    main()

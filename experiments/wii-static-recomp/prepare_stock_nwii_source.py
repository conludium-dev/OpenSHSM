"""Prepare the pinned NWiiRecomp source with the verified IOS signature correction."""
from pathlib import Path
import argparse
import json
import shutil

from export_stock_wii_us_copy import digest


SCANNER = 'nWiiAnalyzer/src/signature_scanner.cpp'
FALSE_SIGNATURE = '        { "IOS_IoctlvAsync", { "9421FF90", "7C0802A6", "9001????", "93E1????", "7CBF2B78", "93C1????", "7C9E2378" } },\n'


def prepare(source_path, destination_path):
    source = Path(source_path).expanduser().resolve(strict=True)
    destination = Path(destination_path).expanduser().absolute()
    if not destination.parent.is_dir():
        raise ValueError('Destination parent does not exist')
    destination = destination.parent.resolve(strict=True) / destination.name
    if destination.exists() or destination.is_symlink() or destination == source or \
            source in destination.parents or destination in source.parents:
        raise ValueError('Destination must be fresh and outside the supplied source')

    manifest_path = Path(__file__).with_name('stock-nwii-source-revision-595f176f.json')
    manifest = json.loads(manifest_path.read_text())
    if manifest['revision'] != '595f176f1d24cc54ff2e8389feed12d7fb553cc2' or \
            len(manifest['files']) != 89:
        raise ValueError('Pinned NWiiRecomp manifest differs')
    original_scanner = (source / SCANNER).read_text()
    scanner = original_scanner
    if FALSE_SIGNATURE in scanner:
        if scanner.count(FALSE_SIGNATURE) != 1:
            raise ValueError('False IOS signature is ambiguous')
        scanner = scanner.replace(FALSE_SIGNATURE, '', 1)
    if digest_bytes(scanner.encode()) != manifest['files'][SCANNER]:
        raise ValueError('IOS signature source differs from the pinned corrected file')
    for name, expected in manifest['files'].items():
        if name != SCANNER and digest(source / name) != expected:
            raise ValueError(f'Pinned NWiiRecomp source differs: {name}')

    destination.mkdir(mode=0o700)
    for name in manifest['files']:
        output = destination / name
        output.parent.mkdir(parents=True, exist_ok=True)
        if name == SCANNER:
            output.write_text(scanner)
        else:
            shutil.copyfile(source / name, output)
        if digest(output) != manifest['files'][name]:
            raise RuntimeError(f'Copied source differs: {name}')
    report = {
        'result': 'PINNED_NWII_SOURCE_PREPARED_NOT_GAME_VERIFIED',
        'revision': manifest['revision'],
        'sourceManifestSha256': digest(manifest_path),
        'falseSignatureRemoved': scanner != original_scanner,
        'scannerSha256': digest(destination / SCANNER),
        'sourceFileCount': len(manifest['files']),
        'limits': ['Build, export and game verification are separate stages.'],
    }
    (destination / 'source-preparation-result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def digest_bytes(data):
    import hashlib
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nwii-source', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    print(prepare(args.nwii_source, args.destination)['result'])


if __name__ == '__main__':
    main()

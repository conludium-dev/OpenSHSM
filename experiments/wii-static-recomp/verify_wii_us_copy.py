"""Validate an extracted owner-supplied Wii US revision 0 DATA tree."""
from pathlib import Path
import argparse
import hashlib
import json


EXPECTED_ID = b'R5WEA4'
EXPECTED_REVISION = 0
EXPECTED_DOL_SHA256 = 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
MANIFEST = Path(__file__).with_name('wii-us-r5wea4-rev0-files.json')


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def data_root(source):
    source = Path(source).expanduser().absolute()
    if source.is_symlink():
        raise ValueError('Source root must be a real directory')
    direct = (source / 'sys/boot.bin').is_file()
    nested = (source / 'DATA/sys/boot.bin').is_file()
    if direct == nested:
        raise ValueError('Choose one extracted DATA directory or its single parent')
    return source if direct else source / 'DATA'


def check_file(root, relative, expected):
    path = root
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError(f'Symlink in game copy: {relative}')
    if not path.is_file() or path.stat().st_size != expected['bytes']:
        raise ValueError(f'Missing or wrong-sized game file: {relative}')
    actual = digest(path)
    if actual != expected['sha256']:
        raise ValueError(f'Game file SHA-256 mismatch: {relative}')
    return actual


def audit_copy(source):
    root = data_root(source)
    if root.is_symlink():
        raise ValueError('DATA directory must not be a symlink')
    boot = root / 'sys/boot.bin'
    if boot.is_symlink():
        raise ValueError('Boot header must not be a symlink')
    with boot.open('rb') as stream:
        header = stream.read(8)
    if len(header) != 8 or header[:6] != EXPECTED_ID or header[7] != EXPECTED_REVISION:
        raise ValueError('Expected Wii US R5WEA4 revision 0 boot header')
    manifest = json.loads(MANIFEST.read_text())
    if manifest['gameId'] != EXPECTED_ID.decode() or manifest['revision'] != EXPECTED_REVISION:
        raise ValueError('Unexpected game manifest identity')
    rows = manifest['files']
    if next(row for row in rows if row['path'] == 'sys/main.dol')['sha256'] != EXPECTED_DOL_SHA256:
        raise ValueError('Unexpected manifest DOL identity')
    if len({row['path'] for row in rows}) != len(rows):
        raise ValueError('Duplicate game file in manifest')
    for row in rows:
        relative = Path(row['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe game file path in manifest')
        check_file(root, relative, row)
    return {'result': 'OWNER_WII_US_R5WEA4_REV0_EXTRACTED_DATA_VERIFIED',
        'source': str(root), 'gameId': manifest['gameId'], 'revision': manifest['revision'],
        'files': len(rows), 'bytes': sum(row['bytes'] for row in rows),
        'manifestSha256': digest(MANIFEST), 'auditorSha256': digest(Path(__file__)),
        'dolSha256': EXPECTED_DOL_SHA256,
        'limits': ['Read-only check of extracted DATA bytes; no game assets copied or packaged.',
            'Does not extract ISO/WBFS, build the recompiler, launch the game or prove playable behavior.',
            'Only Wii US R5WEA4 revision 0 is accepted.']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    try:
        report = audit_copy(args.source)
    except (OSError, ValueError, KeyError, StopIteration) as error:
        raise SystemExit(str(error)) from error
    if args.report:
        destination = args.report.absolute()
        if destination == Path(report['source']) or Path(report['source']) in destination.parents:
            raise SystemExit('Report must be outside the game DATA tree')
        destination.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

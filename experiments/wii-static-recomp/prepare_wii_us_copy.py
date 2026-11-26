"""Stage a verified owner-supplied extracted Wii DATA tree for the existing runtime."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
from verify_wii_us_copy import MANIFEST, audit_copy, data_root, digest


def fresh_destination(destination, source_root=None):
    destination = Path(destination).expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destination already exists; choose a fresh directory')
    if not destination.parent.is_dir():
        raise ValueError('Destination parent does not exist')
    destination = destination.parent.resolve(strict=True) / destination.name
    if source_root is not None:
        root = Path(source_root).resolve(strict=True)
        if destination == root or root in destination.parents:
            raise ValueError('Destination must be outside the original DATA tree')
    return destination


def copy_checked(source, target, expected):
    target.parent.mkdir(parents=True, exist_ok=True)
    value = hashlib.sha256()
    count = 0
    with source.open('rb') as reader, target.open('xb') as writer:
        for block in iter(lambda: reader.read(4 * 1024 * 1024), b''):
            writer.write(block)
            value.update(block)
            count += len(block)
    if count != expected['bytes'] or value.hexdigest() != expected['sha256']:
        raise ValueError(f'Source changed during import: {expected["path"]}')
    shutil.copystat(source, target)


def prepare(source, destination):
    destination = fresh_destination(destination, data_root(source))
    proof = audit_copy(source)
    root = Path(proof['source']).resolve(strict=True)
    free = shutil.disk_usage(destination.parent).free
    if free < proof['bytes'] + 512 * 1024 * 1024:
        raise ValueError('Insufficient free space for verified Wii files')
    manifest = json.loads(MANIFEST.read_text())
    destination.mkdir(mode=0o700)
    partial = destination / '.DATA.partial'
    partial.mkdir(mode=0o700)
    try:
        for row in manifest['files']:
            relative = Path(row['path'])
            copy_checked(root / relative, partial / relative, row)
        imported = audit_copy(partial)
        if imported['manifestSha256'] != proof['manifestSha256']:
            raise ValueError('Import manifest changed during copy')
    except Exception as error:
        raise RuntimeError(f'Import incomplete at {partial}: {error}') from error
    partial.rename(destination / 'DATA')
    report = {'result': 'OWNER_WII_US_R5WEA4_REV0_PRIVATE_DATA_PREPARED',
        'source': str(root), 'destination': str(destination / 'DATA'),
        'files': imported['files'], 'bytes': imported['bytes'],
        'sourceAuditSha256': hashlib.sha256(json.dumps(proof, sort_keys=True).encode()).hexdigest(),
        'manifestSha256': imported['manifestSha256'],
        'preparerSha256': digest(Path(__file__)),
        'limits': ['Private extracted game data, never include DATA in a public source/ZIP package.',
            'No ISO/WBFS extraction, own-DOL compilation, runtime launch or playable acceptance.']}
    (destination / 'import.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def prepare_image(image, dolphin_tool, destination):
    image = Path(image).expanduser().absolute()
    dolphin_tool = Path(dolphin_tool).expanduser().absolute()
    if image.is_symlink() or not image.is_file():
        raise ValueError('Image must be an existing regular file')
    if dolphin_tool.is_symlink() or not dolphin_tool.is_file() or \
            not os.access(dolphin_tool, os.X_OK):
        raise ValueError('DolphinTool must be an executable regular file')
    destination = fresh_destination(destination)
    manifest = json.loads(MANIFEST.read_text())
    required = sum(row['bytes'] for row in manifest['files'])
    if shutil.disk_usage(destination.parent).free < required + 512 * 1024 * 1024:
        raise ValueError('Insufficient free space for extracted Wii files')
    destination.mkdir(mode=0o700)
    log = destination / 'extract.log'
    try:
        with log.open('wb') as output:
            process = subprocess.run([str(dolphin_tool), 'extract',
                '--input', str(image), '--output', str(destination),
                '--gameonly', '--quiet'], stdout=output,
                stderr=subprocess.STDOUT, timeout=3600, check=False)
        if process.returncode != 0:
            raise RuntimeError(f'DolphinTool exited {process.returncode}')
        imported = audit_copy(destination / 'DATA')
    except Exception as error:
        raise RuntimeError(f'Image import incomplete at {destination}; '
            f'inspect {log}: {error}') from error
    report = {'result': 'OWNER_WII_US_R5WEA4_REV0_PRIVATE_IMAGE_PREPARED',
        'sourceImage': str(image), 'destination': str(destination / 'DATA'),
        'files': imported['files'], 'bytes': imported['bytes'],
        'manifestSha256': imported['manifestSha256'],
        'dolphinToolSha256': digest(dolphin_tool),
        'preparerSha256': digest(Path(__file__)),
        'limits': ['Private extracted game data, never include DATA in a public package.',
            'This import requires an external DolphinTool executable.',
            'A verified DATA tree does not prove game launch or playability.']}
    (destination / 'import.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--source', type=Path)
    source.add_argument('--image', type=Path)
    parser.add_argument('--dolphin-tool', type=Path)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.image:
            if not args.dolphin_tool:
                parser.error('--image requires --dolphin-tool')
            report = prepare_image(args.image, args.dolphin_tool, args.destination)
        else:
            if args.dolphin_tool:
                parser.error('--dolphin-tool requires --image')
            report = prepare(args.source, args.destination)
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit(str(error)) from error
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

"""Verify that an exported OpenSHSM repository is source-only and Windows-safe."""
from pathlib import Path, PureWindowsPath
import argparse
import hashlib
import json
import re


FORBIDDEN_PARTS = {'work', '_scratch', 'private-game', '__pycache__', '.git'}
FORBIDDEN_SUFFIXES = {'.dol', '.elf', '.iso', '.rvz', '.wbfs', '.wia', '.gcz', '.bin', '.exe',
    '.dll', '.dylib', '.pdb', '.o', '.obj', '.a', '.lib', '.zip', '.bmp', '.pyc'}
WINDOWS_RESERVED = {'CON', 'PRN', 'AUX', 'NUL',
    *{f'COM{index}' for index in range(1, 10)},
    *{f'LPT{index}' for index in range(1, 10)}}
SECRET_PATTERNS = {
    'AWS access key': re.compile(rb'AKIA[0-9A-Z]{16}'),
    'GitHub token': re.compile(rb'(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}'),
    'OpenAI key': re.compile(rb'sk-[A-Za-z0-9_-]{20,}'),
    'private key': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
}
ABSOLUTE_DEVELOPER_PATH = re.compile(rb'(?:/Users/|/Volumes/|[A-Za-z]:[\\\\/]Users[\\\\/])')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root):
    root = Path(root).expanduser().resolve(strict=True)
    manifest_path = root / 'snapshot-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if manifest['result'] != 'PUBLIC_SOURCE_REPOSITORY_PREPARED_NOT_UPLOADED':
        raise ValueError('Unexpected public snapshot result')
    expected = {row['path']: row for row in manifest['files']}
    actual = {}
    folded = {}
    errors = []
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        relative_text = relative.as_posix()
        if any(part.startswith('._') for part in relative.parts):
            errors.append(f'AppleDouble metadata: {relative_text}')
        if path.is_symlink():
            errors.append(f'symbolic link: {relative_text}')
            continue
        if not path.is_file():
            continue
        if any(part in FORBIDDEN_PARTS for part in relative.parts):
            errors.append(f'private/cache path: {relative_text}')
        if path.suffix.casefold() in FORBIDDEN_SUFFIXES:
            errors.append(f'forbidden binary: {relative_text}')
        if path.name == 'openshsm_owner_qte_payload.h':
            errors.append(f'private generated QTE descriptor: {relative_text}')
        if path.name in ('.env',) or path.name.startswith('.env.'):
            errors.append(f'environment file: {relative_text}')
        key = relative_text.casefold()
        if key in folded:
            errors.append(f'case collision: {folded[key]} and {relative_text}')
        folded[key] = relative_text
        for part in PureWindowsPath(relative_text).parts:
            stem = part.split('.', 1)[0].upper()
            if stem in WINDOWS_RESERVED or part.endswith((' ', '.')) or re.search(r'[<>:"|?*]', part):
                errors.append(f'Windows-incompatible name: {relative_text}')
        if len(str(PureWindowsPath('C:/OpenSHSM') / PureWindowsPath(relative_text))) > 240:
            errors.append(f'Windows path over 240 characters: {relative_text}')
        data = path.read_bytes()
        if relative_text != 'experiments/wii-static-recomp/verify_public_repository.py':
            for label, pattern in SECRET_PATTERNS.items():
                if pattern.search(data):
                    errors.append(f'{label}: {relative_text}')
            if ABSOLUTE_DEVELOPER_PATH.search(data):
                errors.append(f'absolute developer path: {relative_text}')
        if path != manifest_path:
            actual[relative_text] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    if set(actual) != set(expected):
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        errors.append(f'manifest mismatch; missing={missing[:8]} extra={extra[:8]}')
    for name in sorted(set(actual) & set(expected)):
        if actual[name] != {'bytes': expected[name]['bytes'], 'sha256': expected[name]['sha256']}:
            errors.append(f'manifest digest mismatch: {name}')
    required = ['README.md', 'LICENSE.md', 'licenses/OpenSHSM-LICENSE.txt',
        'licenses/NWiiRecomp-LICENSE.txt', 'CONTRIBUTING.md', 'REPOSITORY-CHECKLIST.md',
        '.gitignore', '.gitattributes',
        'OpenSHSM.command', 'experiments/wii-static-recomp/launcher_import.py',
        'experiments/wii-static-recomp/verify_launcher_import.py',
        'OpenSHSM-Windows.ps1', 'experiments/wii-static-recomp/BuildVersion.h',
        'experiments/wii-static-recomp/build_stock_owner_windows.py',
        'experiments/wii-static-recomp/launch_stock_owner_windows.py']
    for name in required:
        if not (root / name).is_file():
            errors.append(f'missing required file: {name}')
    if errors:
        raise ValueError('\n'.join(errors[:80]))
    return {'result': 'PUBLIC_REPOSITORY_SOURCE_ONLY_WINDOWS_PATHS_PASS',
        'files': len(actual), 'bytes': sum(row['bytes'] for row in actual.values()),
        'manifestSha256': digest(manifest_path),
        'limits': ['Static repository audit only; no Windows gameplay was run.',
            'License presence is checked; this is not a legal compatibility audit.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.root), indent=2))


if __name__ == '__main__':
    main()

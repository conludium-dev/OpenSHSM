"""Private disc-context fixture from the user's own extraction, without original-data edits."""
from pathlib import Path
import hashlib
import json
import shutil
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
source = Path('work/private-game/disc/DATA')
output = root / 'dolphin-es-disc'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_es_title_dolphin.py')], check=True)
tmd = (source / 'tmd.bin').read_bytes()
ticket = (source / 'ticket.bin').read_bytes()
boot = (source / 'sys/boot.bin').read_bytes()
header = (source / 'disc/header.bin').read_bytes()
assert len(tmd) >= 0x1e4 and len(ticket) == 0x2a4 and len(boot) >= 0x440 and len(header) == 0x100
assert struct.unpack_from('>I', tmd)[0] == struct.unpack_from('>I', ticket)[0] == 0x10001
title_id = struct.unpack_from('>Q', tmd, 0x18c)[0]
ios_id = struct.unpack_from('>Q', tmd, 0x184)[0]
assert title_id == struct.unpack_from('>Q', ticket, 0x1dc)[0] == 0x0001000052355745
assert boot[:8] == header[:8] == b'R5WEA4\0\0'
assert struct.unpack_from('>I', boot, 0x18)[0] == 0x5d1c9ea3
assert sha(source / 'sys/main.dol') == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
count = struct.unpack_from('>H', tmd, 0x1de)[0]
assert count >= 1 and len(tmd) == 0x1e4 + count * 36
files = ['tmd.bin', 'ticket.bin', 'cert.bin', 'h3.bin', 'disc/header.bin', 'disc/region.bin',
    'sys/boot.bin', 'sys/bi2.bin', 'sys/apploader.img', 'sys/fst.bin']
hashes = {name: sha(source / name) for name in files + ['sys/main.dol']}
for name in files:
    target = output / 'DATA' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        assert sha(target) == hashes[name], 'Never overwrite changed lab metadata'
    else:
        shutil.copyfile(source / name, target)
target = output / 'DATA/sys/main.dol'
harness = root / 'dolphin-es-title/fpr-init.dol'
if target.exists():
    assert sha(target) == sha(harness), 'Never overwrite another lab executable'
else:
    shutil.copyfile(harness, target)
alias = output / 'fpr-init.dol'
if alias.exists():
    assert sha(alias) == sha(harness), 'Never overwrite another verifier fixture'
else:
    shutil.copyfile(harness, alias)
assets = output / 'DATA/files'
if assets.is_symlink():
    assert assets.resolve() == (source / 'files').resolve()
    assets.unlink()
assets.mkdir(exist_ok=True)
asset_records = []
for original in sorted((source / 'files').rglob('*')):
    assert not original.is_symlink(), 'Never follow unexpected original asset links'
    target = assets / original.relative_to(source / 'files')
    if original.is_dir():
        target.mkdir(exist_ok=True)
        continue
    assert original.is_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        cloned = subprocess.run(['cp', '-c', str(original), str(target)], capture_output=True, text=True)
        if cloned.returncode != 0:
            assert not target.exists(), 'Do not overwrite a partial clone'
            shutil.copyfile(original, target)
    assert target.is_file() and target.stat().st_size == original.stat().st_size
    assert target.stat().st_ino != original.stat().st_ino, 'Never use asset hardlinks'
    asset_records.append({'name': str(original.relative_to(source / 'files')), 'bytes': original.stat().st_size, 'separateInode': True})
assert all(sha(source / name) == digest for name, digest in hashes.items())
report = {'preparerSha256': sha(Path(__file__)), 'originalSourceHashes': hashes,
    'gameID': boot[:6].decode('ascii'), 'revision': boot[7], 'titleId': f'{title_id:016x}', 'iosId': f'{ios_id:016x}',
    'titleVersion': struct.unpack_from('>H', tmd, 0x1dc)[0], 'contentCount': count,
    'harnessSha256': sha(output / 'DATA/sys/main.dol'), 'standaloneHarnessSha256': sha(harness),
    'assetsDirectory': str(assets), 'assetCopies': asset_records,
    'runnerSha256': sha(experiment / 'run_es_disc_dolphin.ps1'),
    'references': ['https://github.com/dolphin-emu/dolphin/blob/2609/Source/Core/Core/IOS/ES/Formats.h',
        'https://github.com/dolphin-emu/dolphin/blob/2609/Source/Core/DiscIO/DirectoryBlob.cpp',
        'https://github.com/dolphin-emu/dolphin/blob/2609/Source/Core/Core/IOS/ES/ES.cpp'],
    'limits': ['Structural identity/hash checks only, no TMD/ticket signature or content-chain cryptographic verification.',
        'Private separate asset copies (copy-on-write where supported); original DOL replaced ONLY in lab by the unchanged SDK harness.',
        'Ticket keys/certificates never printed or published; disc context still requires execution and response verification.']}
(output / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
print('Prepared private disc fixture:', report['gameID'], 'revision', report['revision'], 'title', report['titleId'], 'IOS', report['iosId'])

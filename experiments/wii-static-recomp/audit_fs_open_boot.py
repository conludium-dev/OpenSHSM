"""Fresh original-reply and enabled/disabled gates for the exact fourth FS OPEN."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'mass-fs-open-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
for verifier in ('verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py'):
    subprocess.run(['python3', str(experiment / verifier)], check=True)
build = json.loads((output / 'build.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_fs_open_boot.py')
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
base_path = root / 'mass-exi-sync-ee-boot/build.json'
assert build['baseBuildSha256'] == sha(base_path)
base = json.loads(base_path.read_text())
assert len(build['records']) == 125
assert [row['file'] for row, old in zip(build['records'], base['records']) if row != old] == ['output_62.cpp', 'output_67.cpp']
for row, old in zip(build['records'], base['records']):
    assert row['sourceSha256'] == old['sourceSha256']
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
oracle = json.loads((root / 'dolphin-fs-pending/comparison.json').read_text())
exe = output / 'openshsm-mass-boot'
assert sha(exe) == build['executableSha256']
results = {}
for mode in ('live', 'disabled'):
    env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
    if mode == 'disabled':
        env['SHSM_FS_OPEN_DISABLED'] = '1'
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(output / 'boot-quarantine.tsv'),
        str(root / 'sram-native/settings.bin')], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 7 and not result.stderr
    log = output / (mode + '-boot.log')
    log.write_text(result.stdout)
    lines = result.stdout.splitlines()
    assert 'BOOT_STM_ASYNC dispatched=1 pending=1 6 1 324927520 4096 4796512 32 4796544 32' in lines
    for view, key in (('PHYSICAL', 'physicalPacketHex'), ('CACHED', 'cachedPacketHex')):
        line = next(line for line in lines if line.startswith('BOOT_STM_ASYNC_' + view + ' '))
        assert bytes(map(int, line.split()[1:])).hex() == oracle['initialPending'][key]
    if mode == 'live':
        assert 'BOOT_FS_REPLY 2 935e0060 50' in lines
        assert 'BOOT_FS_LAYOUT 2 1 935e1000 1' in lines
        assert 'BOOT_STM submitted=8 produced=3' in lines and 'BOOT_SI_DELIVERY entries=11 callbacks=4' in lines
        assert 'BOOT_STM_NEXT_PATH /dev/es' in lines
        for view, key in (('PHYSICAL', 'replyPhysicalHex'), ('CACHED', 'replyCachedHex')):
            line = next(line for line in lines if line.startswith('BOOT_FS_' + view + ' '))
            assert bytes(map(int, line.split()[1:])).hex() == oracle['observations'][0][key]
    else:
        assert 'BOOT_STM submitted=6 produced=2' in lines and not any(line.startswith('BOOT_FS_REPLY') for line in lines)
        assert 'BOOT_FS_LAYOUT ffffffff 0 935e1000 0' in lines
        assert 'BOOT_NEXT_OPEN_PATH_PHYSICAL 47 100 101 118 47 102 115 0' in lines
    boundary = next(line for line in lines if line.startswith('BOOT_BOUNDARY '))
    assert boundary.startswith('BOOT_BOUNDARY pc=80241c30 lr=80242384 msr=2032') and 'STM sender caller/value unverified' in boundary
    results[mode] = {'boundary': boundary, 'logSha256': sha(log)}
    print(mode + ': ' + boundary)
(output / 'audit.json').write_text(json.dumps({'result': 'WHOLE_BOOT_FS_OPEN_REPLY_ORIGINAL_MATCH_ISFS_FLAGS_PENDING_STM_RETAINED',
    'verifierSha256': sha(Path(__file__)), 'buildSha256': sha(output / 'build.json'), 'results': results,
    'oracleSha256': sha(root / 'dolphin-fs-pending/comparison.json'), 'ackProofSha256': sha(root / 'dolphin-fs-ack/comparison.json'),
    'limits': ['Exactly fourth /dev/fs OPEN; next /dev/es stopped before submission. Native event/loader timing is a PC adaptation.',
        'No original physical Wii/whole retail startup/FS IOCTL/file/STM callback completion or first-screen proof.']}, indent=2) + '\n')

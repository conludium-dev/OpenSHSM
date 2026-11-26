"""Validate actual ES reply/SDK FD store and the disabled fifth-OPEN control."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import struct

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'mass-es-open-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_es_pending_dolphin.py')], check=True)
build = json.loads((output / 'build.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_es_open_boot.py')
assert build['parentBuilderSha256'] == sha(experiment / 'build_fs_open_boot.py')
base_path = root / 'mass-fs-open-boot/build.json'
assert build['baseBuildSha256'] == sha(base_path)
base = json.loads(base_path.read_text())
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
assert len(build['records']) == 125
assert [row['file'] for row, old in zip(build['records'], base['records']) if row != old] == ['output_62.cpp', 'output_67.cpp']
for row, old in zip(build['records'], base['records']):
    assert row['sourceSha256'] == old['sourceSha256']
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
oracle_path = root / 'dolphin-es-pending/comparison.json'
oracle = json.loads(oracle_path.read_text())
exe = output / 'openshsm-mass-boot'
assert sha(exe) == build['executableSha256']
results = {}
for mode in ('live', 'disabled'):
    env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
    if mode == 'disabled':
        env['SHSM_ES_OPEN_DISABLED'] = '1'
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(output / 'boot-quarantine.tsv'),
        str(root / 'sram-native/settings.bin')], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 7 and not result.stderr
    log = output / (mode + '-boot.log')
    log.write_text(result.stdout)
    lines = result.stdout.splitlines()
    assert 'BOOT_STM_ASYNC dispatched=1 pending=1 6 1 324927520 4096 4796512 32 4796544 32' in lines
    assert 'BOOT_FS_REPLY 2 935e0060 50' in lines and 'BOOT_FS_LAYOUT 2 1 935e1000 1' in lines
    for view, key in (('PHYSICAL', 'physicalPacketHex'), ('CACHED', 'cachedPacketHex')):
        line = next(line for line in lines if line.startswith('BOOT_STM_ASYNC_' + view + ' '))
        assert bytes(map(int, line.split()[1:])).hex() == oracle['initialPending'][key]
    boundary = next(line for line in lines if line.startswith('BOOT_BOUNDARY '))
    if mode == 'live':
        assert 'BOOT_ES_REPLY 3 935e0060 50' in lines and 'BOOT_ES_LAYOUT 3' in lines
        assert 'BOOT_STM submitted=10 produced=4' in lines and 'BOOT_SI_DELIVERY entries=13 callbacks=4' in lines
        for view, key in (('PHYSICAL', 'replyPhysicalHex'), ('CACHED', 'replyCachedHex')):
            line = next(line for line in lines if line.startswith('BOOT_ES_' + view + ' '))
            assert bytes(map(int, line.split()[1:])).hex() == oracle['observations'][1][key]
        assert boundary.startswith('BOOT_BOUNDARY pc=80212ff4 lr=80242fc8 msr=a032') and 'EE flush caller/pending-state unverified' in boundary
        cached = next(line for line in lines if line.startswith('BOOT_ES_NEXT_CACHED '))
        physical = next(line for line in lines if line.startswith('BOOT_ES_NEXT_PHYSICAL '))
        cached_bytes = bytes(map(int, cached.split()[1:]))
        assert struct.unpack_from('>8I', cached_bytes) == (7, 3, 3, 0x20, 0, 1, 0x8053fff0, 0)
        assert bytes(map(int, physical.split()[1:])).hex() == oracle['observations'][1]['replyPhysicalHex']
    else:
        assert 'BOOT_ES_LAYOUT ffffffff' in lines and 'BOOT_STM submitted=8 produced=3' in lines
        assert not any(line.startswith('BOOT_ES_REPLY') for line in lines)
        assert 'BOOT_STM_NEXT_PATH /dev/es' in lines
        assert boundary.startswith('BOOT_BOUNDARY pc=80241c30 lr=80242384 msr=2032')
    results[mode] = {'boundary': boundary, 'logSha256': sha(log)}
    print(mode + ': ' + boundary)
(output / 'audit.json').write_text(json.dumps({'result': 'NATIVE_ES_OPEN_ORIGINAL_REPLY_FD3_PENDING_STM_DISABLED_CONTROL_PASS',
    'verifierSha256': sha(Path(__file__)), 'buildSha256': sha(output / 'build.json'), 'oracleSha256': sha(oracle_path), 'results': results,
    'limits': ['Only ES OPEN and source ESP FD store/continuation; next ioctl-vector cache flush still guarded before submission.',
        'No ES IOCTL/IOCTLV result, title/ticket/certificate data, cycle-accurate or full retail/gameplay equivalence.']}, indent=2) + '\n')

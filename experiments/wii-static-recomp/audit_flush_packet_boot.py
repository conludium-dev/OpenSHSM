"""Audit fresh packet-caller admission, previous profile and source-preserving controls."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

root = Path('work/private-game/static-recomp')
output = root / 'mass-flush-packet-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert build['builderSha256'] == sha(Path('experiments/wii-static-recomp/build_flush_packet_boot.py'))
assert build['baseBuildSha256'] == sha(root / 'mass-ipc-startup-boot/build.json')
assert build['profileBuildSha256'] == sha(root / 'flush-packet-profile/build.json')
assert build['nativeProofSha256'] == sha(root / 'flush-packet-profile/comparison.json')
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256']
    assert sha(Path(row['object'])) == row['objectSha256']
assert build['executableSha256'] == sha(output / 'openshsm-mass-boot')
assert build['quarantineSha256'] == sha(root / 'mass-ipc-startup-boot/boot-quarantine.tsv')
fresh = {}
for mode in ('live', 'packet-disabled', 'ee-disabled'):
    environment = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
    if mode == 'packet-disabled':
        environment['SHSM_FLUSH_PACKET_DISABLED'] = '1'
    elif mode == 'ee-disabled':
        environment['SHSM_FLUSH_EE_DISABLED'] = '1'
    result = subprocess.run([str(output / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol',
        str(output / 'boot-quarantine.tsv'), str(root / 'sram-native/settings.bin')], env=environment,
        capture_output=True, text=True, timeout=30)
    (output / (mode + '-boot.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 7 and not result.stderr
    log = result.stdout
    assert 'BOOT_SI_DELIVERY entries=4 callbacks=4' in log
    assert 'BOOT_FINITE_MEM2 steps=1765312 returned=1' in log
    assert 'BOOT_IPC_STARTUP writes=1 control=38' in log
    boundary = next(line for line in log.splitlines() if line.startswith('BOOT_BOUNDARY '))
    expected = {'packet-disabled': ('80242240', 4), 'ee-disabled': ('8024262c', 3)}
    if mode in expected:
        caller, count = expected[mode]
        assert f'pc=80212ff4 lr={caller} msr=a032' in boundary
        assert 'EE flush caller/pending-state unverified' in boundary
        assert f'BOOT_FLUSH entries={count} phase=0 barriers={count}' in log
    else:
        assert 'BOOT_FLUSH entries=5 phase=0 barriers=5' in log
        assert 'pc=80241c30 lr=80242384 msr=2032' in boundary
        assert 'BAT MMIO/locked-cache/unmapped backing access unavailable' in boundary
    fresh[mode] = boundary
(output / 'audit.json').write_text(json.dumps({'result': 'PACKET_MEM2_FLUSH_RETURNS_NEXT_BOUNDARY_RETAINED',
    'buildSha256': sha(output / 'build.json'), 'auditorSha256': sha(Path(__file__)), 'freshBoundaries': fresh,
    'limits': ['No complete IPC client/request behavior or original firstscreen/menu/audio proof.']}, indent=2) + '\n')
print('\n'.join(mode + ': ' + boundary for mode, boundary in fresh.items()))

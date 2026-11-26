"""Fresh enabled/disabled boot audit with unchanged function bytes and quarantine."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

root = Path('work/private-game/static-recomp')
output = root / 'mass-flush-ee-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert build['builderSha256'] == sha(Path('experiments/wii-static-recomp/build_flush_ee_boot.py'))
assert build['baseBuildSha256'] == sha(root / 'mass-ipc-startup-boot/build.json')
assert build['profileBuildSha256'] == sha(root / 'flush-ee-profile/build.json')
assert build['nativeProofSha256'] == sha(root / 'flush-ee-profile/comparison.json')
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256']
    assert sha(Path(row['object'])) == row['objectSha256']
assert build['executableSha256'] == sha(output / 'openshsm-mass-boot')
assert build['quarantineSha256'] == sha(root / 'mass-ipc-startup-boot/boot-quarantine.tsv')
fresh = {}
for mode in ('live', 'disabled'):
    environment = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
    if mode == 'disabled':
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
    if mode == 'disabled':
        assert 'pc=80212ff4 lr=8024262c msr=a032' in boundary
        assert 'EE flush caller/pending-state unverified' in boundary
        assert 'BOOT_FLUSH entries=3 phase=0 barriers=3' in log
    else:
        assert 'BOOT_FLUSH entries=4 phase=0 barriers=4' in log
        assert 'pc=80212ff4 lr=80242240 msr=a032' in boundary
        assert 'EE flush caller/pending-state unverified' in boundary
    fresh[mode] = boundary
(output / 'audit.json').write_text(json.dumps({'result': 'ORIGINAL_EE_FLUSH_RETURNS_NEXT_BOUNDARY_RETAINED',
    'buildSha256': sha(output / 'build.json'), 'auditorSha256': sha(Path(__file__)), 'freshBoundaries': fresh,
    'limits': ['No pending interrupt concurrency or complete IPC init proof.',
        'No original first screen/menu/audio or stage2-4 completion.']}, indent=2) + '\n')
print('\n'.join(mode + ': ' + boundary for mode, boundary in fresh.items()))

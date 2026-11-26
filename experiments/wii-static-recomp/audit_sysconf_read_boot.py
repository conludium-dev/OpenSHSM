"""Compare actual nested native READ callbacks, complete data and original ownership order."""
from pathlib import Path
import base64
import hashlib
import json
import os
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'mass-sysconf-read-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
base_path = root / 'mass-sysconf-open-boot/build.json'
base = json.loads(base_path.read_text())
assert build['builderSha256'] == sha(experiment / 'build_sysconf_read_boot.py')
assert build['baseBuildSha256'] == sha(base_path)
assert build['parentBuilderSha256'] == sha(experiment / 'build_fs_open_boot.py')
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
assert len(build['records']) == 125
assert [row['file'] for row, old in zip(build['records'], base['records']) if row != old] == [
    'output_62.cpp', 'output_63.cpp', 'output_67.cpp']
for row, old in zip(build['records'], base['records']):
    assert row['sourceSha256'] == old['sourceSha256']
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for name in ('stm_device.cpp', 'es_device.cpp'):
    assert sha(output / name) == sha(base_path.parent / name)
lab = Path('_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF')
assert sha(lab) == build['laboratoryConsoleFileSha256'] == base['laboratoryConsoleFileSha256']
data = lab.read_bytes()
oracle_path = root / 'dolphin-sysconf-events-fixed-disc/fpr-init-true-dolphin.json'
oracle = json.loads(oracle_path.read_text(encoding='utf-8-sig'))
raw = base64.b64decode(oracle['events'])
events = [raw[64 + i * 1280:64 + (i + 1) * 1280] for i in range(115)]
assert base64.b64decode(oracle['confPhysical']) == data


def check(lines, enabled):
    def one(prefix):
        matches = [line for line in lines if line.startswith(prefix + ' ')]
        assert len(matches) == 1, prefix
        return matches[0][len(prefix) + 1:].split()

    assert one('SC_OPEN_API_RETURN') == ['0', 'a032', '1', '31']
    assert 'BOOT_STM_ASYNC dispatched=1 pending=1 6 1 324927520 4096 4796512 32 4796544 32' in lines
    assert 'BOOT_ES_CLOSE_STATE ffffffff 935e0060 50' in lines
    assert 'BOOT_NAND_INIT_STATE 2' in lines
    boundary = ' '.join(one('BOOT_BOUNDARY'))
    assert boundary.startswith('pc=80212ff4 lr=80242240 msr=32')
    assert 'Flush syscall CPU/site/profile unverified' in boundary
    if not enabled:
        assert 'BOOT_STM submitted=18 produced=8' in lines
        assert one('BOOT_FLUSH') == ['entries=24', 'phase=0', 'barriers=18']
        assert not any(line.startswith('SC_READ_CALLBACK ') or line.startswith('SC_READ_FREE ') for line in lines)
        return
    assert 'BOOT_STM submitted=20 produced=9' in lines
    assert one('BOOT_FLUSH') == ['entries=25', 'phase=0', 'barriers=19']
    assert 'BOOT_SI_DELIVERY entries=23 callbacks=4' in lines
    sequence = [line for line in lines if line.startswith(('SC_READ_FREE ', 'SC_READ_CALLBACK '))]
    assert sequence == ['SC_READ_FREE 1 935e1020 32', 'SC_READ_FREE 0 935e0080 32',
        'SC_READ_CALLBACK 80240680 4000 935e1180 32', 'SC_READ_CALLBACK 80247800 4000 804b3094 32']
    for index, address in ((64, '80240680'), (65, '80247800')):
        for view, offset in (('CACHED', 192), ('PHYSICAL', 256)):
            assert bytes(map(int, one('SC_READ_REPLY_' + view + ' ' + address))) == events[index][offset:offset + 64]
    for view in ('CACHED', 'PHYSICAL'):
        assert bytes(map(int, one('SC_READ_BUFFER_' + view))) == data


exe = output / 'openshsm-mass-boot'
assert sha(exe) == build['executableSha256']
observations = {}
for mode in ('live', 'disabled'):
    env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
    env['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'
    env['SHSM_SC_LAB_FILE'] = str(lab)
    if mode == 'disabled':
        env['SHSM_SYSCONF_READ_DISABLED'] = '1'
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(output / 'boot-quarantine.tsv'),
        str(root / 'sram-native/settings.bin')], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 7 and not result.stderr
    (output / (mode + '-audit.log')).write_text(result.stdout)
    observations[mode] = result.stdout.splitlines()
    check(observations[mode], mode == 'live')
mutants = 0
for prefix in ('SC_READ_FREE 1', 'SC_READ_FREE 0', 'SC_READ_CALLBACK 80240680', 'SC_READ_CALLBACK 80247800',
    'SC_READ_REPLY_CACHED 80240680', 'SC_READ_REPLY_PHYSICAL 80240680', 'SC_READ_BUFFER_CACHED',
    'SC_READ_BUFFER_PHYSICAL', 'SC_OPEN_API_RETURN', 'BOOT_STM_ASYNC dispatched='):
    changed = [line for line in observations['live'] if not line.startswith(prefix)]
    try:
        check(changed, True)
    except AssertionError:
        mutants += 1
    else:
        raise AssertionError('Corrupted observation accepted: ' + prefix)
(output / 'audit.json').write_text(json.dumps({'verifierSha256': sha(Path(__file__)),
    'buildSha256': sha(output / 'build.json'), 'oracleSha256': sha(oracle_path),
    'dataSha256': sha(lab), 'mutants': mutants, 'result': 'NATIVE_NESTED_READ_16384_CALLBACK2_MSR32_ORIGINAL_BYTES_OWNERSHIP_PASS',
    'limits': ['PC X1 consumption and ACK64/reply65 timing; CSR3a observed in native after final38, not claimed physical trace equivalence.',
        'Next original CLOSE is prepared but not submitted. SC parse/completion/product file not reached.']}, indent=2) + '\n')
print('PASS native nestedREAD16384/both full buffers/original64replies/callback2-MSR32/oldOPEN frees ordered/STM/disabled;10mutants')

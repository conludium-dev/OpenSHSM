"""Verify async return-before-ACK and three original callback layers in native boot."""
from pathlib import Path
import base64
import hashlib
import json
import os
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'mass-sysconf-open-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
base_path = root / 'mass-sysconf-path-boot/build.json'
base = json.loads(base_path.read_text())
assert build['builderSha256'] == sha(experiment / 'build_sysconf_open_boot.py')
assert build['baseBuildSha256'] == sha(base_path)
assert build['parentBuilderSha256'] == sha(experiment / 'build_fs_open_boot.py')
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
assert len(build['records']) == 125
assert [row['file'] for row, old in zip(build['records'], base['records']) if row != old] == [
    'output_62.cpp', 'output_63.cpp', 'output_67.cpp']
for row, old in zip(build['records'], base['records']):
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    if row['file'] == 'output_67.cpp':
        added = '\n    nwii::runtime::experiment_sysconf_return_observe(ctx);'
        text = Path(row['source']).read_text()
        assert text.count(added) == 1 and text.replace(added, '') == Path(old['source']).read_text()
    else:
        assert row['sourceSha256'] == old['sourceSha256']
for name in ('stm_device.cpp', 'es_device.cpp', 'flush_syscall.h'):
    assert sha(output / name) == sha(base_path.parent / name)
lab = Path('_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF')
assert sha(lab) == build['laboratoryConsoleFileSha256']
oracle_path = root / 'dolphin-sysconf-events-fixed-disc/fpr-init-true-dolphin.json'
oracle = json.loads(oracle_path.read_text(encoding='utf-8-sig'))
raw = base64.b64decode(oracle['events'])
events = [raw[64 + i * 1280:64 + (i + 1) * 1280] for i in range(115)]


def check(lines, enabled):
    def one(prefix):
        matches = [line for line in lines if line.startswith(prefix + ' ')]
        assert len(matches) == 1, prefix
        return matches[0][len(prefix) + 1:].split()

    assert 'BOOT_STM_ASYNC dispatched=1 pending=1 6 1 324927520 4096 4796512 32 4796544 32' in lines
    assert 'BOOT_ES_CLOSE_STATE ffffffff 935e0060 50' in lines
    assert 'BOOT_NAND_INIT_STATE 2' in lines
    boundary = ' '.join(one('BOOT_BOUNDARY'))
    if not enabled:
        assert 'BOOT_STM submitted=16 produced=7' in lines
        assert boundary.startswith('pc=80241c30 lr=80242384 msr=2032')
        assert 'STM sender caller/value unverified' in boundary
        assert not any(line.startswith('SC_OPEN_CALLBACK') or line.startswith('SC_OPEN_API_RETURN') for line in lines)
        return
    assert 'BOOT_STM submitted=18 produced=8' in lines
    assert one('SC_OPEN_API_RETURN') == ['0', 'a032', '1', '31']
    callbacks = [line for line in lines if line.startswith('SC_OPEN_CALLBACK ')]
    expected_callbacks = ['SC_OPEN_CALLBACK 80240680 32 3 935e1020 935e00c0',
        'SC_OPEN_CALLBACK 80244e30 32 3 804b3094 935e00c0',
        'SC_OPEN_CALLBACK 80247730 32 0 804b3094 935e00c0']
    assert callbacks == expected_callbacks
    assert lines.index('SC_OPEN_API_RETURN 0 a032 1 31') < lines.index(callbacks[0])
    for index, address in zip((52, 53, 54), ('80240680', '80244e30', '80247730')):
        for view, offset in [('PHYSICAL', 128), ('CACHED', 64)]:
            expected = bytearray(events[index][offset:offset + 64])
            struct.pack_into('>I', expected, 24, 0x80540010)
            assert bytes(map(int, one('SC_OPEN_REPLY_' + view + ' ' + address))) == expected
    assert bytes(map(int, one('SC_NESTED_READ_CACHED'))) == events[55][192:256]
    assert one('SC_OPEN_FILEINFO') == ['3', '935e0120', '802464b0', '804b3094']
    assert one('BOOT_FLUSH') == ['entries=24', 'phase=0', 'barriers=18']
    assert boundary.startswith('pc=80212ff4 lr=80242240 msr=32')
    assert 'Flush syscall CPU/site/profile unverified' in boundary


exe = output / 'openshsm-mass-boot'
assert sha(exe) == build['executableSha256']
observations = {}
for mode in ('live', 'disabled'):
    env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
    env['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'
    env['SHSM_SC_LAB_FILE'] = str(lab)
    if mode == 'disabled':
        env['SHSM_SYSCONF_OPEN_DISABLED'] = '1'
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol',
        str(output / 'boot-quarantine.tsv'), str(root / 'sram-native/settings.bin')],
        env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 7 and not result.stderr
    (output / (mode + '-audit.log')).write_text(result.stdout)
    observations[mode] = result.stdout.splitlines()
    check(observations[mode], mode == 'live')
mutants = 0
for prefix in ('SC_OPEN_API_RETURN', 'SC_OPEN_CALLBACK 80240680', 'SC_OPEN_CALLBACK 80244e30',
    'SC_OPEN_CALLBACK 80247730', 'SC_OPEN_REPLY_CACHED 80240680', 'SC_OPEN_REPLY_PHYSICAL 80240680',
    'SC_NESTED_READ_CACHED', 'SC_OPEN_FILEINFO', 'BOOT_STM_ASYNC dispatched='):
    changed = [line for line in observations['live'] if not line.startswith(prefix)]
    try:
        check(changed, True)
    except AssertionError:
        mutants += 1
    else:
        raise AssertionError('Corrupted observation accepted: ' + prefix)
(output / 'audit.json').write_text(json.dumps({'verifierSha256': sha(Path(__file__)),
    'buildSha256': sha(output / 'build.json'), 'oracleSha256': sha(oracle_path), 'mutants': mutants,
    'result': 'NATIVE_ASYNC_OPEN_RETURN_BEFORE_ACK_CALLBACK3_REENTRANT_READ_PREPARED_PASS',
    'limits': ['ACK64/reply65 scheduler ticks are explicit PC timing adaptation, not original cycle accuracy.',
        'Nested READ stops before its MSR32 packet flush; old work/packet remain allocated. Laboratory console file is not a release dependency.']}, indent=2) + '\n')
print('PASS actual asyncOPEN/API0-beforeACK/callback3-MSR32/original64replies/nestedREAD allocations/STM/disabled;9mutants')

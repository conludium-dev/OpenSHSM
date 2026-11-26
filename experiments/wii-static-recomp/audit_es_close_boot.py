"""Verify actual first native ES CLOSE and original source FD invalidation."""
from pathlib import Path
import hashlib
import json
import os
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'mass-es-close-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
base_path = root / 'mass-es-datadir-boot/build.json'
base = json.loads(base_path.read_text())
assert build['builderSha256'] == sha(experiment / 'build_es_close_boot.py')
assert build['parentBuilderSha256'] == sha(experiment / 'build_fs_open_boot.py')
assert build['baseBuildSha256'] == sha(base_path)
assert build['adapterSha256'] == sha(experiment / 'es_close_adapter.h')
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
assert len(build['records']) == 125
assert [row['file'] for row, old in zip(build['records'], base['records']) if row != old] == ['output_62.cpp', 'output_67.cpp']
for row, old in zip(build['records'], base['records']):
    assert row['sourceSha256'] == old['sourceSha256']
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for name in ('es_device.cpp', 'fs_device.cpp', 'stm_device.cpp', 'flush_syscall.h'):
    assert sha(output / name) == sha(base_path.parent / name)
oracle_path = root / 'dolphin-es-close-disc/disc-comparison.json'
oracle = json.loads(oracle_path.read_text())
case = oracle['cases'][0]
assert case['kind'] == 'ESP_CloseLib' and case['returnValue'] == 0 and case['sdkFd'] == -1
pending = json.loads((root / 'dolphin-es-pending/comparison.json').read_text())['initialPending']
exe = output / 'openshsm-mass-boot'
assert sha(exe) == build['executableSha256']


def check(lines, enabled):
    def values(prefix):
        matches = [line for line in lines if line.startswith(prefix + ' ')]
        assert len(matches) == 1, prefix
        return matches[0].split()[1:]

    for view, key in (('PHYSICAL', 'physicalPacketHex'), ('CACHED', 'cachedPacketHex')):
        assert bytes(map(int, values('BOOT_STM_ASYNC_' + view))).hex() == pending[key]
    assert 'BOOT_FS_REPLY 2 935e0060 50' in lines and 'BOOT_ES_REPLY 3 935e0060 50' in lines
    assert 'BOOT_DATADIR_HEAP 935e0060 50' in lines and 'BOOT_DATADIR_CONTINUATION 8019d564 8024635c' in lines
    path = bytes(map(int, values('BOOT_DATADIR_OUTPUT_CACHED')))
    assert path == b'/title/00010000/52355745/data' + bytes(3)
    assert bytes(map(int, values('BOOT_DATADIR_OUTPUT_PHYSICAL'))) == path
    assert 'BOOT_STM_ASYNC dispatched=1 pending=1 6 1 324927520 4096 4796512 32 4796544 32' in lines
    boundary = ' '.join(values('BOOT_BOUNDARY'))
    if enabled:
        assert values('BOOT_ES_CLOSE_AT') == ['80218c00', '8024637c']
        assert values('BOOT_ES_CLOSE_STATE') == ['ffffffff', '935e0060', '50']
        for view, key in (('PHYSICAL', 'physicalReplyHex'), ('CACHED', 'cachedReplyHex')):
            expected = bytearray.fromhex(case[key])
            struct.pack_into('>I', expected, 24, 0x80540010)
            assert bytes(map(int, values('BOOT_ES_CLOSE_' + view))) == expected
        assert 'BOOT_NAND_INIT_STATE 2' in lines and 'BOOT_ES_LAYOUT ffffffff' in lines
        assert 'BOOT_STM submitted=16 produced=7' in lines and 'BOOT_SI_DELIVERY entries=19 callbacks=4' in lines
        assert values('BOOT_NEXT_OPEN_ASYNC_ARGS') == ['935e1020', '1', '80240680', '935e1020']
        assert bytes(map(int, values('BOOT_NEXT_OPEN_ASYNC_PATH'))) == b'/shared2/sys/SYSCONF'.ljust(64, b'\0')
        assert boundary.startswith('pc=80212ff4 lr=8024250c msr=a032') and 'EE flush caller/pending-state unverified' in boundary
    else:
        assert not any(line.startswith('BOOT_ES_CLOSE_STATE ') for line in lines)
        assert not any(line.startswith('BOOT_NAND_INIT_STATE ') for line in lines)
        assert 'BOOT_ES_LAYOUT 3' in lines and 'BOOT_STM submitted=14 produced=6' in lines
        assert 'BOOT_SI_DELIVERY entries=17 callbacks=4' in lines
        assert boundary.startswith('pc=80241c30 lr=80242384 msr=2032') and 'STM sender caller/value unverified' in boundary
    return boundary


results, logs = {}, {}
for mode in ('live', 'disabled'):
    env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
    env['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'
    if mode == 'disabled':
        env['SHSM_ES_CLOSE_DISABLED'] = '1'
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(output / 'boot-quarantine.tsv'),
        str(root / 'sram-native/settings.bin')], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 7 and not result.stderr
    log = output / (mode + '-boot.log')
    log.write_text(result.stdout)
    logs[mode] = result.stdout.splitlines()
    results[mode] = {'boundary': check(logs[mode], mode == 'live'), 'logSha256': sha(log)}
mutants = 0
for prefix, index in [('BOOT_ES_CLOSE_PHYSICAL', 1), ('BOOT_ES_CLOSE_CACHED', 25), ('BOOT_ES_CLOSE_STATE', 1),
    ('BOOT_ES_CLOSE_STATE', 2), ('BOOT_NAND_INIT_STATE', 1), ('BOOT_STM_ASYNC_CACHED', 33),
    ('BOOT_NEXT_OPEN_ASYNC_PATH', 1)]:
    changed = list(logs['live'])
    slot = next(i for i, line in enumerate(changed) if line.startswith(prefix + ' '))
    parts = changed[slot].split()
    parts[index] = format(int(parts[index], 16) ^ 1, 'x') if prefix == 'BOOT_ES_CLOSE_STATE' else str(int(parts[index]) ^ 1)
    changed[slot] = ' '.join(parts)
    try:
        check(changed, True)
    except AssertionError:
        mutants += 1
assert mutants == 7
(output / 'audit.json').write_text(json.dumps({'result': 'NATIVE_FIRST_ES_CLOSE_SOURCE_FD_INVALIDATION_NAND_STATE2_PASS',
    'verifierSha256': sha(Path(__file__)), 'buildSha256': sha(output / 'build.json'), 'oracleSha256': sha(oracle_path),
    'results': results, 'rejectedObservationMutants': mutants,
    'limits': ['First CLOSE only. Physical reply correctly retains ignored virtual vector pointer; oracle/native pointer relocated explicitly.',
        'NANDInit state2 reached, not file/save IO, SYSCONF support, first image or full retail/physical-Wii equivalence.']}, indent=2) + '\n')
print('PASS native ES CLOSE/sourceFD-1/NANDstate2/both64 replies/heap/STM/disabled;7mutants; next SYSCONF async path flush guarded')

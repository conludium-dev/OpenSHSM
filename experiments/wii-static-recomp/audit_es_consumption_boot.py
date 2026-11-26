"""Audit real original ES16 return/count and source cleanup against the LAB oracle."""
from pathlib import Path
import base64
import hashlib
import json
import os
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
base = root / 'mass-es-consumption-flush-boot'
output = root / 'mass-es-consumption-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
for verifier in ('verify_es_consumption_dolphin.py', 'verify_es_consumption_device.py', 'verify_es_consumption_flush_guard.py'):
    subprocess.run(['python3', str(experiment / verifier)], check=True)
build = json.loads((output / 'build.json').read_text())
previous = json.loads((base / 'build.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_es_consumption_boot.py')
assert sha(output / 'openshsm-mass-boot') == build['executableSha256']
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
assert (output / 'es_consumption_dispatch.h').read_bytes() == (experiment / 'es_consumption_dispatch.h').read_bytes()
assert len(build['records']) == len(previous['records']) == 125
for row, old in zip(build['records'], previous['records']):
    assert row['file'] == old['file']
    expected = Path(old['source']).read_text()
    if row['file'] == 'output_68.cpp':
        for label, kind in [('loc_80249CE0: ;', 1), ('loc_80249D98: ;', 2)]:
            expected = expected.replace(label, label + '\n    nwii::runtime::experiment_es_consumption_observe(ctx, ' + str(kind) + ');')
    assert Path(row['source']).read_text() == expected
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    if row['file'] not in ('output_62.cpp', 'output_67.cpp', 'output_68.cpp'):
        assert row['object'] == old['object']
for name in ('es_device.cpp', 'di_device.cpp', 'stm_device.cpp', 'flush_syscall.h'):
    assert (output / name).read_bytes() == (base / name).read_bytes()
logs = {}
for mode in ('live', 'disabled'):
    env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
    env.update(SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin', SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin',
        SHSM_ES_LAB_CONSUMPTION='1', SHSM_DI_LAB_INQUIRY_PATH=str(root / 'di-inquiry-device/dolphin-lab-inquiry.bin'),
        SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF',
        SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')
    if mode == 'disabled':
        env['SHSM_ES_CONSUMPTION_DISABLED'] = '1'
    result = subprocess.run([str(output / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol',
        str(output / 'boot-quarantine.tsv'), str(root / 'sram-native/settings.bin')], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 7 and not result.stderr
    logs[mode] = result.stdout
    (output / (mode + '-audit.log')).write_text(result.stdout)
live, disabled = logs['live'], logs['disabled']
assert 'BOOT_STM submitted=40 produced=19' in live and 'BOOT_STM submitted=38 produced=18' in disabled
assert 'BOOT_BOUNDARY pc=80241c30 lr=80242384 msr=2032' in live and 'BOOT_BOUNDARY pc=80241c30 lr=80242384 msr=2032' in disabled
assert 'BOOT_SI_DELIVERY entries=43 callbacks=4' in live
assert 'ES16_SOURCE 2' not in disabled and 'ES16_SERVICE_COUNT_AFTER' not in disabled
assert 'ES16_SOURCE 1 1e93e ae49af75 0 8053fde0 a032 8053fde0 935e0060' in live
assert 'ES16_SOURCE 2 0 2032 a032 935e0060 a032 8053fde0 935e0060' in live
assert live.index('ES16_SOURCE 1 ') < live.index('ES16_SERVICE_COUNT_BEFORE ') < live.index('ES16_SERVICE_COUNT_AFTER ') < live.index('ES16_SOURCE 2 ')
assert live.splitlines().count('ES16_SERVICE_COUNT_BEFORE 8053fcf0') == 1
assert live.splitlines().count('ES16_SERVICE_COUNT_AFTER 0') == 1

def payload(log, prefix):
    matches = [line[len(prefix):] for line in log.splitlines() if line.startswith(prefix)]
    assert len(matches) == 1, prefix
    return bytes(map(int, matches[0].split()))

oracle_path = root / 'dolphin-es-consumption-disc/fpr-init-true-dolphin.json'
oracle = json.loads(oracle_path.read_text(encoding='utf-8-sig'))
assert struct.unpack('>2I', base64.b64decode(oracle['consumptionScalarsPhysical'])[:8]) == (0, 0x2032)
assert payload(live, 'ES16_CALLER 2 ') == base64.b64decode(oracle['consumptionCountPhysical'])[:4]
for cache, vector in [('CACHED', 0x8053fd70), ('PHYSICAL', 0x53fd70)]:
    assert payload(live, 'ES16_REPLY_' + cache + ' ') == struct.pack('>8I', 8, 0, 7, 0x16, 1, 2, vector, 0) + bytes(32)
for prefix, size in [('SC_COMPLETE_CONF_CACHED ', 16384), ('SC_COMPLETE_CONF_PHYSICAL ', 16384),
    ('SC_COMPLETE_PRODUCT_CACHED ', 256), ('SC_COMPLETE_PRODUCT_PHYSICAL ', 256),
    ('ES_TICKET_CALLER_CACHED ', 216), ('BOOT_STM_ASYNC_CACHED ', 64), ('BOOT_STM_ASYNC_PHYSICAL ', 64)]:
    assert len(payload(live, prefix)) == size and payload(live, prefix) == payload(disabled, prefix)
for kind in range(1, 5):
    for tag in ('INQUIRY_REPLY_CACHED ', 'INQUIRY_REPLY_PHYSICAL ', 'INQUIRY_DATA_CACHED ', 'INQUIRY_DATA_PHYSICAL '):
        prefix = tag + str(kind) + ' '
        assert payload(live, prefix) == payload(disabled, prefix)
(output / 'consumption-audit.json').write_text(json.dumps({'result': 'ORIGINAL_PPC_ES16_KERNEL_API0_CALLER_COUNT0_FREE0060_PASS',
    'auditSha256': sha(Path(__file__)), 'buildSha256': sha(output / 'build.json'),
    'oracleSha256': sha(oracle_path), 'liveLogSha256': sha(output / 'live-audit.log'), 'disabledLogSha256': sha(output / 'disabled-audit.log'),
    'limits': ['Same kernel/device/events return response; original SDK copies count0 and retires packet/freehead0060 before return.',
        'Native caller MSRA032 vs original2032 remains an explicit context difference, not normalized.',
        'Ticket-ID/NULL-array/count4 LAB policy is not general physical IOS behavior.',
        'Three objects rebuilt122 retained; only68 adds two read-only PPC observations; no forced guest state/results.',
        'Next request remains before sender; no first screen/fullgame/physical Wii timing claim.']}, indent=2) + '\n')
print('PASS fresh native original ES16 API0/count0/source cleanup0060; actual kernel stale count overwritten; 40-19 vs disabled38-18')

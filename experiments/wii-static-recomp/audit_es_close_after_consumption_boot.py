"""Audit real original post-ES16 close return/SDK FD clearing and unchanged buffers."""
from pathlib import Path
import base64
import hashlib
import json
import os
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
base = root / 'mass-es-consumption-boot'
output = root / 'mass-es-close-after-consumption-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
for verifier in ('verify_es_close_after_consumption_dolphin.py', 'verify_es_close_after_consumption_kernel.py'):
    subprocess.run(['python3', str(experiment / verifier)], check=True)
build = json.loads((output / 'build.json').read_text())
previous = json.loads((base / 'build.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_es_close_after_consumption_boot.py')
assert build['executableSha256'] == sha(output / 'openshsm-mass-boot')
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
assert (output / 'es_close_after_consumption_adapter.h').read_bytes() == (experiment / 'es_close_after_consumption_adapter.h').read_bytes()
assert len(build['records']) == len(previous['records']) == 125
for row, old in zip(build['records'], previous['records']):
    assert row['file'] == old['file']
    expected = Path(old['source']).read_text()
    if row['file'] == 'output_68.cpp':
        for label, kind in [('loc_802497F0: ;', 1), ('loc_80249834: ;', 2)]:
            expected = expected.replace(label, label + '\n    nwii::runtime::experiment_post_consumption_close_observe(ctx, ' + str(kind) + ');')
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
        env['SHSM_POST_ES16_CLOSE_DISABLED'] = '1'
    result = subprocess.run([str(output / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol',
        str(output / 'boot-quarantine.tsv'), str(root / 'sram-native/settings.bin')], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 7 and not result.stderr
    logs[mode] = result.stdout
    (output / (mode + '-audit.log')).write_text(result.stdout)
live, disabled = logs['live'], logs['disabled']
assert 'BOOT_STM submitted=42 produced=20' in live
assert 'BOOT_STM submitted=40 produced=19' in disabled
assert 'BOOT_BOUNDARY pc=80212ff4 lr=8024250c msr=a032' in live
assert 'BOOT_BOUNDARY pc=80241c30 lr=80242384 msr=2032' in disabled
assert 'BOOT_SI_DELIVERY entries=45 callbacks=4' in live
assert live.splitlines().count('POST_ES16_CLOSE_SOURCE 1 0 a032 4 935e0060') == 1
assert live.splitlines().count('POST_ES16_CLOSE_SOURCE 2 0 a032 ffffffff 935e0060') == 1
assert live.index('ES16_SOURCE 2 ') < live.index('POST_ES16_CLOSE_SOURCE 1 ') < live.index('POST_ES16_CLOSE_SOURCE 2 ')
assert 'POST_ES16_CLOSE_SOURCE 2' not in disabled
assert 'POST_ES16_CLOSE_CACHED' not in disabled

def payload(log, prefix):
    matches = [line[len(prefix):] for line in log.splitlines() if line.startswith(prefix)]
    assert len(matches) == 1, prefix
    return bytes(map(int, matches[0].split()))

oracle_path = root / 'dolphin-es-close-after-consumption-disc/fpr-init-true-dolphin.json'
oracle = json.loads(oracle_path.read_text(encoding='utf-8-sig'))
assert base64.b64decode(oracle['closeScalarsPhysical']) == struct.pack('>3I', 0, 0x2032, 0xffffffff) + bytes(20)
packet = struct.pack('>8I', 8, 0, 2, 0x16, 1, 2, 0x8053fd70, 0) + bytes(32)
for cache in ('CACHED', 'PHYSICAL'):
    assert payload(live, 'POST_ES16_CLOSE_' + cache + ' ') == packet
for prefix, size in [('SC_COMPLETE_CONF_CACHED ', 16384), ('SC_COMPLETE_CONF_PHYSICAL ', 16384),
    ('SC_COMPLETE_PRODUCT_CACHED ', 256), ('SC_COMPLETE_PRODUCT_PHYSICAL ', 256),
    ('ES_TICKET_CALLER_CACHED ', 216), ('ES16_CALLER 2 ', 4), ('ES16_REPLY_CACHED ', 64),
    ('ES16_REPLY_PHYSICAL ', 64), ('BOOT_STM_ASYNC_CACHED ', 64), ('BOOT_STM_ASYNC_PHYSICAL ', 64)]:
    assert len(payload(live, prefix)) == size and payload(live, prefix) == payload(disabled, prefix)
for kind in range(1, 5):
    for tag in ('INQUIRY_REPLY_CACHED ', 'INQUIRY_REPLY_PHYSICAL ', 'INQUIRY_DATA_CACHED ', 'INQUIRY_DATA_PHYSICAL '):
        prefix = tag + str(kind) + ' '
        assert payload(live, prefix) == payload(disabled, prefix)
(output / 'close-audit.json').write_text(json.dumps({'result': 'ORIGINAL_PPC_POST_ES16_CLOSE_API0_SDK_FD_MINUS1_FREE0060_PASS',
    'auditSha256': sha(Path(__file__)), 'buildSha256': sha(output / 'build.json'), 'oracleSha256': sha(oracle_path),
    'liveLogSha256': sha(output / 'live-audit.log'), 'disabledLogSha256': sha(output / 'disabled-audit.log'),
    'limits': ['Actual existing kernel.close FD4; original SDK clearsFD-1 and frees packet, no host FD/state forcing.',
        'Both64 replies preserve ignored old16/1/2/virtualvector fields, not another ioctlv.',
        'Native caller A032 versus original2032 remains explicit context difference.',
        'Three objects rebuilt122 retained; only68 two read-only PPC hooks; all previous full buffers/pending STM preserved.',
        'Next asynchronous-open flush remains guarded; no first screen/fullgame/physical IOS timing claim.']}, indent=2) + '\n')
print('PASS fresh native original CLOSE FD4 API0/SDKFD-1/free0060/reply64x2; enabled42-20 vs disabled40-19; previous buffers retained')

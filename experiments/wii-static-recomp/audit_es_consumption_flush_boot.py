"""Audit original ES16 flush-to-sender and preservation of the completed boot chain."""
from pathlib import Path
import hashlib
import json
import os
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
base = root / 'mass-di-inquiry-boot'
output = root / 'mass-es-consumption-flush-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
for verifier in ('verify_es_consumption_dolphin.py', 'verify_es_consumption_device.py'):
    subprocess.run(['python3', str(experiment / verifier)], check=True)
build = json.loads((output / 'build.json').read_text())
old_build = json.loads((base / 'build.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_es_consumption_flush_boot.py')
assert sha(output / 'openshsm-mass-boot') == build['executableSha256']
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
for name in ('es_consumption_flush.h', 'es_consumption_adapter.h'):
    assert (output / name).read_bytes() == (experiment / name).read_bytes()
assert len(build['records']) == len(old_build['records']) == 125
for row, old in zip(build['records'], old_build['records']):
    assert row['file'] == old['file'] and row['sourceSha256'] == old['sourceSha256']
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    if row['file'] not in ('output_62.cpp', 'output_63.cpp', 'output_67.cpp'):
        assert row['object'] == old['object']
expected = (base / 'flush_syscall.h').read_text().replace('#include "es_di_ticket_flush.h"',
    '#include "es_di_ticket_flush.h"\n#include "es_consumption_flush.h"').replace(
    '!experiment_es_di_ticket_flush(context))', '!experiment_es_di_ticket_flush(context) && !experiment_es_consumption_flush(context))')
assert (output / 'flush_syscall.h').read_text() == expected
for name in ('ipc_ack_frontend.h', 'si_external_delivery.h', 'boot-wrapper.cpp', 'di_device.cpp', 'stm_device.cpp'):
    assert (output / name).read_bytes() == (base / name).read_bytes()
assert (output / 'es_device.cpp').read_bytes() == (root / 'es-consumption-device/es_device.cpp').read_bytes()
logs = {}
for mode in ('live', 'disabled'):
    env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
    env.update(SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin', SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin',
        SHSM_ES_LAB_CONSUMPTION='1', SHSM_DI_LAB_INQUIRY_PATH=str(root / 'di-inquiry-device/dolphin-lab-inquiry.bin'),
        SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF',
        SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')
    if mode == 'disabled':
        env['SHSM_ES_CONSUMPTION_FLUSH_DISABLED'] = '1'
    result = subprocess.run([str(output / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol',
        str(output / 'boot-quarantine.tsv'), str(root / 'sram-native/settings.bin')], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 7 and not result.stderr
    logs[mode] = result.stdout
    (output / (mode + '-audit.log')).write_text(result.stdout)
live, disabled = logs['live'], logs['disabled']
assert 'BOOT_BOUNDARY pc=80241c30 lr=80242384 msr=2032' in live
assert 'reason=STM sender caller/value unverified' in live
assert 'BOOT_BOUNDARY pc=80212ff4 lr=80242fc8 msr=a032' in disabled
for log in logs.values():
    assert 'BOOT_STM submitted=38 produced=18' in log
    assert 'INQUIRY_SOURCE_FREE 0 935e00e0 32 0' in log
    assert 'INQUIRY_SOURCE 4 0 32 32 0 935e0060 0 20 8002' in log

def payload(log, prefix):
    matches = [line[len(prefix):] for line in log.splitlines() if line.startswith(prefix)]
    assert len(matches) == 1, prefix
    return bytes(map(int, matches[0].split()))

packet = struct.pack('>8I', 7, 0, 4, 0x16, 1, 2, 0x53fd70, 0) + bytes(32)
for cache in ('CACHED', 'PHYSICAL'):
    assert payload(live, 'ES16_PACKET_' + cache + ' ') == packet
    assert payload(live, 'ES16_VECTOR_' + cache + ' ') == struct.pack('>6I', 0x53fca0, 8, 0, 0, 0x53fcc0, 4)
for prefix, size in [('SC_COMPLETE_CONF_CACHED ', 16384), ('SC_COMPLETE_CONF_PHYSICAL ', 16384),
    ('SC_COMPLETE_PRODUCT_CACHED ', 256), ('SC_COMPLETE_PRODUCT_PHYSICAL ', 256),
    ('ES_TICKET_CALLER_CACHED ', 216), ('BOOT_STM_ASYNC_CACHED ', 64), ('BOOT_STM_ASYNC_PHYSICAL ', 64)]:
    assert len(payload(live, prefix)) == size and payload(live, prefix) == payload(disabled, prefix)
for kind in range(1, 5):
    for tag in ('INQUIRY_REPLY_CACHED ', 'INQUIRY_REPLY_PHYSICAL ', 'INQUIRY_DATA_CACHED ', 'INQUIRY_DATA_PHYSICAL '):
        prefix = tag + str(kind) + ' '
        assert payload(live, prefix) == payload(disabled, prefix)
(output / 'flush-audit.json').write_text(json.dumps({'result': 'ORIGINAL_ES16_OUTPUT_INPUT_VECTOR_PACKET_FLUSH_TO_SENDER_PASS',
    'auditSha256': sha(Path(__file__)), 'buildSha256': sha(output / 'build.json'),
    'liveLogSha256': sha(output / 'live-audit.log'), 'disabledLogSha256': sha(output / 'disabled-audit.log'),
    'limits': ['All125 PPC sources unchanged; three objects rebuilt/122 retained.',
        'Original SDK normalizes and flushes ES16 packet; both64 views coherent, no host pointer/register rewrite.',
        'Previous complete files/ticket/inquiry and pendingSTM preserved.',
        'Component ES16 verified but native PPC request still not submitted; next sender must be admitted separately.',
        'LAB PC policy is not physical IOS consumption/cache timing, first screen or full game.']}, indent=2) + '\n')
print('PASS fresh ES16 original output/input/vector/packet flush-to-sender; sources125/122retained/control buffers preserved; request NOT submitted')

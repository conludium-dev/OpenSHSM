"""Audit unchanged PPC source and real ticket-vector flush to pre-submission boundary."""
from pathlib import Path
import hashlib
import json
import os
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
base = root / 'mass-di-burst-cache-boot'
output = root / 'mass-es-di-ticket-flush-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
for verifier in ('verify_es_di_ticket_device.py', 'verify_es_di_ticket_flush_guard.py'):
    subprocess.run(['python3', str(experiment / verifier)], check=True)
build = json.loads((output / 'build.json').read_text())
previous = json.loads((base / 'build.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_es_di_ticket_flush_boot.py')
assert sha(output / 'openshsm-mass-boot') == build['executableSha256']
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
assert len(build['records']) == 125
for row, old in zip(build['records'], previous['records']):
    assert row['file'] == old['file'] and row['sourceSha256'] == old['sourceSha256']
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    if row['file'] not in ('output_62.cpp', 'output_63.cpp', 'output_67.cpp'):
        assert row['object'] == old['object']
old = (base / 'flush_syscall.h').read_text()
expected = old.replace('#include "stm_async_dispatch.h"', '#include "stm_async_dispatch.h"\n#include "es_di_ticket_flush.h"').replace(
    '&& !sysconfPathFlush)', '&& !sysconfPathFlush && !experiment_es_di_ticket_flush(context))')
assert (output / 'flush_syscall.h').read_text() == expected
assert (output / 'es_device.cpp').read_bytes() == (root / 'es-di-ticket-device/es_device.cpp').read_bytes()
assert (output / 'ipc_ack_frontend.h').read_bytes() == (base / 'ipc_ack_frontend.h').read_bytes()
logs = {}
for mode in ('live', 'disabled'):
    env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
    env.update(SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin', SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin',
        SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF',
        SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')
    if mode == 'disabled':
        env['SHSM_ES_DI_TICKET_FLUSH_DISABLED'] = '1'
    result = subprocess.run([str(output / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol',
        str(output / 'boot-quarantine.tsv'), str(root / 'sram-native/settings.bin')], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 7 and not result.stderr
    logs[mode] = result.stdout
    (output / (mode + '-audit.log')).write_text(result.stdout)
live, disabled = logs['live'], logs['disabled']
assert 'BOOT_BOUNDARY pc=80241c30 lr=80242384 msr=2032' in live
assert 'reason=STM sender caller/value unverified' in live
assert 'BOOT_BOUNDARY pc=80212ff4 lr=80242fc8 msr=a032' in disabled
assert 'BOOT_STM submitted=36 produced=16' in live and 'BOOT_STM submitted=36 produced=16' in disabled
expected_packet = struct.pack('>8I', 7, 1, 4, 0x1b, 1, 1, 0x53ff10, 0) + bytes(32)
for tag in ('DI_BURST_REPLY_CACHED', 'DI_BURST_REPLY_PHYSICAL'):
    line = next(line for line in live.splitlines() if line.startswith(tag + ' '))
    assert bytes(map(int, line.split()[1:])) == expected_packet
(output / 'flush-audit.json').write_text(json.dumps({'result': 'TICKET_OUTPUT_VECTOR_PACKET_FLUSH_NATIVE_PRE_SUBMISSION_PASS',
    'auditSha256': sha(Path(__file__)), 'buildSha256': sha(output / 'build.json'),
    'liveLogSha256': sha(output / 'live-audit.log'), 'disabledLogSha256': sha(output / 'disabled-audit.log'),
    'limits': ['All125 PPC sources unchanged; three objects rebuilt/122 retained.',
        'Original SDK flushes/normalizes packet; both64 views equal before first ticket sender, no host packet writes.',
        'Existing ES service component verified, but ticket request NOT submitted or completed in PPC runtime.',
        'Inquiry remains unfinished; no first screen or physical-controller verification.']}, indent=2) + '\n')
print('PASS fresh native two ticket flushes/packet64x2 coherent/125sources122retained/disabled old boundary; NEXT sender, no1B response yet')

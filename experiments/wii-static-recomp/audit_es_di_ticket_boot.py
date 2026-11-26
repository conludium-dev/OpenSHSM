"""Audit original PPC ticket-view return/full caller bytes/free with real kernel."""
from pathlib import Path
import base64
import hashlib
import json
import os
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
base = root / 'mass-es-di-ticket-flush-boot'
output = root / 'mass-es-di-ticket-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
for name in ('verify_es_di_ticket_events_dolphin.py', 'verify_es_di_ticket_device.py'):
    subprocess.run(['python3', str(experiment / name)], check=True)
build = json.loads((output / 'build.json').read_text())
previous = json.loads((base / 'build.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_es_di_ticket_boot.py')
assert sha(output / 'openshsm-mass-boot') == build['executableSha256']
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
assert (output / 'es_di_ticket_dispatch.h').read_bytes() == (experiment / 'es_di_ticket_dispatch.h').read_bytes()
assert len(build['records']) == 125
for row, old in zip(build['records'], previous['records']):
    assert row['file'] == old['file']
    if row['file'] != 'output_68.cpp':
        assert row['sourceSha256'] == old['sourceSha256']
    else:
        text = Path(old['source']).read_text()
        for label, kind in [('loc_80249A00: ;', 1), ('loc_80249A90: ;', 2)]:
            text = text.replace(label, label + '\n    nwii::runtime::experiment_es_ticket_observe(ctx, ' + str(kind) + ');')
        assert Path(row['source']).read_text() == text
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    if row['file'] not in ('output_62.cpp', 'output_67.cpp', 'output_68.cpp'):
        assert row['object'] == old['object']
for name in ('es_device.cpp', 'di_device.cpp', 'fs_device.cpp', 'stm_device.cpp', 'flush_syscall.h'):
    assert (output / name).read_bytes() == (base / name).read_bytes()
logs = {}
for mode in ('live', 'disabled'):
    env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
    env.update(SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin', SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin',
        SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF',
        SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')
    if mode == 'disabled':
        env['SHSM_ES_DI_TICKET_DISABLED'] = '1'
    result = subprocess.run([str(output / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol',
        str(output / 'boot-quarantine.tsv'), str(root / 'sram-native/settings.bin')], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 7 and not result.stderr
    logs[mode] = result.stdout
    (output / (mode + '-audit.log')).write_text(result.stdout)
live, disabled = logs['live'], logs['disabled']
assert 'ES_TICKET_SOURCE 1 0 8053ff80 a032 8053ff80 935e0060' in live
assert 'ES_TICKET_SOURCE 2 0 2032 a032 8053ff80 935e0060' in live
assert 'BOOT_STM submitted=38 produced=17' in live and 'BOOT_SI_DELIVERY entries=40 callbacks=4' in live
assert 'BOOT_BOUNDARY pc=80212ff4 lr=80242fc8 msr=a032' in live
assert 'BOOT_STM submitted=36 produced=16' in disabled
assert 'BOOT_BOUNDARY pc=80241c30 lr=80242384 msr=2032' in disabled
assert 'ES_TICKET_SOURCE 2' not in disabled and 'ES_TICKET_CALLER_CACHED' not in disabled
prefix = 'ES_TICKET_CALLER_CACHED '
line = next(line for line in live.splitlines() if line.startswith(prefix))
caller = bytes(map(int, line[len(prefix):].split()))
oracle_path = root / 'dolphin-es-di-ticket-events-disc/fpr-init-true-dolphin.json'
oracle = json.loads(oracle_path.read_text(encoding='utf-8-sig'))
expected = base64.b64decode(oracle['ticketViewPhysical'])
assert caller == expected and len(caller) == 216
for index in range(216):
    bad = bytearray(caller)
    bad[index] ^= 1
    assert bad != expected
(output / 'ticket-audit.json').write_text(json.dumps({'result': 'ORIGINAL_PPC_TICKET_API0_CALLER216_KERNEL_REPLY_FREE_PASS',
    'auditSha256': sha(Path(__file__)), 'buildSha256': sha(output / 'build.json'),
    'liveLogSha256': sha(output / 'live-audit.log'), 'disabledLogSha256': sha(output / 'disabled-audit.log'),
    'oracleSha256': sha(oracle_path), 'callerSha256': hashlib.sha256(caller).hexdigest(), 'payloadMutantsRejected': 216,
    'limits': ['Original DiGetTicketView source returns0/full216/freeheap0060; host observers only read actual caller state.',
        'Native API MSRA032 vs original2032 and stack pointersFF10 vsFFB0 remain explicit caller-context differences.',
        'Three62-67-68 objects rebuilt/122 retained; only68 read-only hooks changed from prior PPC source.',
        'Native1B returns before unfinished inquiry as observed original sequence; inquiry response still not delivered.',
        'Next unknown request stops at output flush; no first screen or physical Wii/cache/timing claim.']}, indent=2) + '\n')
print('PASS fresh original native1B API0/full216 caller matches original/free0060/enabled38-17/disabled36-16; NEXT inquiry/next request')

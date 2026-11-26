"""Audit native original inquiry callbacks against the captured original DOL trace."""
from pathlib import Path
import base64
import hashlib
import json
import os
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'mass-di-inquiry-boot'
base = root / 'mass-es-di-ticket-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
for name in ('verify_es_di_ticket_events_dolphin.py', 'verify_di_inquiry_device.py'):
    subprocess.run(['python3', str(experiment / name)], check=True)
build = json.loads((output / 'build.json').read_text())
previous = json.loads((base / 'build.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_di_inquiry_boot.py')
assert build['executableSha256'] == sha(output / 'openshsm-mass-boot')
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
for name in ('di_inquiry_adapter.h', 'di_inquiry_runtime.h'):
    assert (output / name).read_bytes() == (experiment / name).read_bytes()
assert len(build['records']) == len(previous['records']) == 125
rebuilt = ('output_62.cpp', 'output_63.cpp', 'output_64.cpp', 'output_65.cpp', 'output_67.cpp', 'output_68.cpp')
for row, old in zip(build['records'], previous['records']):
    assert row['file'] == old['file']
    text = Path(old['source']).read_text()
    if row['file'] == 'output_63.cpp':
        text = text.replace('nwii::runtime::experiment_di_burst_cache_operation(ctx, ctx.gpr[3], 470);',
            'nwii::runtime::experiment_inquiry_cache_operation(ctx, ctx.gpr[3], 470);')
        text = text.replace('loc_80211060: ;', 'loc_80211060: ;\n    nwii::runtime::experiment_inquiry_observe(ctx, 3);')
    if row['file'] == 'output_64.cpp':
        text = text.replace('loc_80222F80: ;', 'loc_80222F80: ;\n    nwii::runtime::experiment_inquiry_observe(ctx, 2);')
    if row['file'] == 'output_65.cpp':
        for label, kind in [('loc_802258A0: ;', 1), ('loc_80225940: ;', 4)]:
            text = text.replace(label, label + '\n    nwii::runtime::experiment_inquiry_observe(ctx, ' + str(kind) + ');')
    if row['file'] == 'output_68.cpp':
        text = text.replace('nwii::runtime::experiment_es_ticket_observe(ctx, 2);',
            'nwii::runtime::experiment_es_ticket_observe(ctx, 2);\n    nwii::runtime::experiment_inquiry_ticket_return(ctx);')
    assert Path(row['source']).read_text() == text, row['file']
    assert sha(Path(row['source'])) == row['sourceSha256']
    assert sha(Path(row['object'])) == row['objectSha256']
    if row['file'] not in rebuilt:
        assert row['object'] == old['object']
oracle_path = root / 'dolphin-es-di-ticket-events-disc/fpr-init-true-dolphin.json'
oracle = json.loads(oracle_path.read_text(encoding='utf-8-sig'))
raw = base64.b64decode(oracle['events'])
events = [raw[64 + i * 1280:64 + (i + 1) * 1280] for i in range(126)]
expected_data = base64.b64decode(oracle['inquiryPhysical'])
logs = {}
for mode in ('live', 'disabled'):
    env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
    env.update(SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin',
        SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin',
        SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF',
        SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt',
        SHSM_DI_LAB_INQUIRY_PATH=str(root / 'di-inquiry-device/dolphin-lab-inquiry.bin'))
    if mode == 'disabled':
        env['SHSM_DI_INQUIRY_DISABLED'] = '1'
    result = subprocess.run([str(output / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol',
        str(output / 'boot-quarantine.tsv'), str(root / 'sram-native/settings.bin')],
        env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 7 and not result.stderr
    logs[mode] = result.stdout
    (output / (mode + '-audit.log')).write_text(result.stdout)
live, disabled = logs['live'], logs['disabled']
assert 'BOOT_STM submitted=38 produced=18' in live
assert 'BOOT_STM submitted=38 produced=17' in disabled
assert 'INQUIRY_SOURCE ' not in disabled and 'INQUIRY_SOURCE_FREE' not in disabled
for log in logs.values():
    assert 'BOOT_BOUNDARY pc=80212ff4 lr=80242fc8 msr=a032' in log
    assert 'ES_TICKET_SOURCE 2 0 2032 a032 8053ff80 935e0060' in log

def payload(log, prefix):
    matches = [line[len(prefix):] for line in log.splitlines() if line.startswith(prefix)]
    assert len(matches) == 1, prefix
    return bytes(map(int, matches[0].split()))

for kind, index in enumerate((121, 122, 123, 124), 1):
    row = events[index]
    words = [struct.unpack_from('>I', row, offset)[0] for offset in (24, 28, 16, 360, 36, 684, 704)]
    revision = struct.unpack_from('>H', row, 1078)[0]
    assert revision == (0x8201 if kind < 4 else 0x8002)
    native_revision = 0 if kind < 4 else revision
    expected = 'INQUIRY_SOURCE ' + str(kind) + ' ' + ' '.join(format(value, 'x') for value in words + [native_revision])
    assert live.splitlines().count(expected) == 1, expected
    assert payload(live, 'INQUIRY_REPLY_CACHED ' + str(kind) + ' ') == row[192:256]
    assert payload(live, 'INQUIRY_REPLY_PHYSICAL ' + str(kind) + ' ') == row[256:320]
    for cache in ('CACHED', 'PHYSICAL'):
        assert payload(live, 'INQUIRY_DATA_' + cache + ' ' + str(kind) + ' ') == expected_data == row[640:672]
assert live.index('ES_TICKET_SOURCE 2 ') < live.index('INQUIRY_SOURCE 1 ')
assert live.index('INQUIRY_SOURCE 1 ') < live.index('INQUIRY_SOURCE 2 ') < live.index('INQUIRY_SOURCE 3 ') < live.index('INQUIRY_SOURCE 4 ') < live.index('INQUIRY_SOURCE_FREE ')
assert live.splitlines().count('INQUIRY_SOURCE_FREE 0 935e00e0 32 0') == 1
assert payload(live, 'ES_TICKET_CALLER_CACHED ') == base64.b64decode(oracle['ticketViewPhysical'])
for name, size in (('PRODUCT', 256), ('CONF', 16384)):
    for cache in ('CACHED', 'PHYSICAL'):
        prefix = 'SC_COMPLETE_' + name + '_' + cache + ' '
        saved = payload(disabled, prefix)
        assert len(saved) == size and payload(live, prefix) == saved
for cache in ('CACHED', 'PHYSICAL'):
    prefix = 'BOOT_STM_ASYNC_' + cache + ' '
    assert len(payload(live, prefix)) == 64
    assert payload(live, prefix) == payload(disabled, prefix)
(output / 'inquiry-audit.json').write_text(json.dumps({
    'result': 'ORIGINAL_PPC_INQUIRY_CALLBACKS_PACKETS_DATA32_BLOCK_AND_REVISION_PASS',
    'auditSha256': sha(Path(__file__)), 'buildSha256': sha(output / 'build.json'),
    'oracleSha256': sha(oracle_path), 'liveLogSha256': sha(output / 'live-audit.log'),
    'disabledLogSha256': sha(output / 'disabled-audit.log'),
    'limits': ['Original callbacks execute without host callback/state/result/register forcing.',
        'Source free call is observed, not proof of every allocator postcondition.',
        'Explicit Dolphin LAB metadata is not physical Wii drive identity or public game dependency.',
        'Input dcbi native MSR2030 vs original30 preserves FP context; bounded adapter is a PC inference.',
        'Ticket native caller A032 differs from original2032; no normalization.',
        'Pre-callback boot revision original8201 vs native0 is an existing LAB initial-state difference; final8002 matches.',
        'Six objects rebuilt/119 retained; later output flush remains guarded; no first screen.']}, indent=2) + '\n')
print('PASS fresh native inquiry: four original callbacks, all packet/data bytes, block0/length32/revision8002, source free call; disabled38-17/live38-18')

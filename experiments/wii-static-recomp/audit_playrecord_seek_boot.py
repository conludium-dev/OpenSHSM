"""Audit SEEK0 and exact callback entries; alarm/SEEK retirement remain incomplete."""
from pathlib import Path
import base64
import hashlib
import json
import os
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
base = root / 'mass-playrecord-read-boot'
output = root / 'mass-playrecord-seek-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
old = json.loads((base / 'build.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_playrecord_seek_boot.py')
assert build['baseBuildSha256'] == sha(base / 'build.json')
assert build['executableSha256'] == sha(output / 'openshsm-mass-boot')
for path,digest in {**build['sourceHashes'],**build['headerHashes']}.items():
    assert sha(Path(path)) == digest
for name in ('playrecord_seek_flush.h','playrecord_seek_dispatch.h'):
    assert (output / name).read_bytes() == (experiment / name).read_bytes()
assert len(build['records']) == len(old['records']) == 125
for row,prior in zip(build['records'],old['records']):
    assert row['file'] == prior['file']
    expected = Path(prior['source']).read_text()
    if row['file'] == 'output_67.cpp':
        for label,kind in [('loc_80240680: ;',1),('loc_802407D0: ;',3),('loc_802438B0: ;',4)]:
            expected = expected.replace(label,label + '\n    nwii::runtime::experiment_playrecord_seek_observe(ctx,' + str(kind) + ');')
    if row['file'] == 'output_64.cpp':
        expected = expected.replace('loc_8021CDE0: ;','loc_8021CDE0: ;\n    nwii::runtime::experiment_playrecord_seek_observe(ctx,2);')
    assert Path(row['source']).read_text() == expected
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    if row['file'] not in ('output_62.cpp','output_63.cpp','output_64.cpp','output_67.cpp','output_68.cpp'):
        assert row == prior
for name in ('fs_device.cpp','di_device.cpp','es_device.cpp','stm_device.cpp','processor_adapter.cpp',
    'ni_guard.h','playrecord_read_dispatch.h','playrecord_read_flush.h','boot-quarantine.tsv'):
    assert (output / name).read_bytes() == (base / name).read_bytes()
capture_path = root / 'dolphin-playrecord-events-disc/fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
events = base64.b64decode(capture['events'])
lab = root / 'playrecord-fs-device/pc-owned-playrecord.bin'
seed_hash = sha(lab)
logs = {}
for mode in ('live','disabled'):
    env = {key:value for key,value in os.environ.items() if not key.startswith('SHSM_')}
    env.update(SHSM_PLAYRECORD_LAB_FILE=str(lab),SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin',
        SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin',SHSM_ES_LAB_CONSUMPTION='1',
        SHSM_DI_LAB_INQUIRY_PATH=str(root / 'di-inquiry-device/dolphin-lab-inquiry.bin'),
        SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF',
        SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')
    if mode == 'disabled':
        env['SHSM_PLAYRECORD_SEEK_DISABLED'] = '1'
    result = subprocess.run([str(output / 'openshsm-mass-boot'),'work/private-game/disc/DATA/sys/main.dol',
        str(output / 'boot-quarantine.tsv'),str(root / 'sram-native/settings.bin')],
        env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode == 7 and not result.stderr
    logs[mode] = result.stdout
    (output / (mode + '-audit.log')).write_text(result.stdout)
assert 'BOOT_BOUNDARY pc=802106e0 lr=80212078 msr=32' in logs['live']
assert 'reason=UNVERIFIED_PROCESSOR_REGISTER_22' in logs['live']
assert 'BOOT_STM submitted=48 produced=23' in logs['live']
assert 'PLAYRECORD_SEEK_END_STATE  4 1 0 0 0 0 0 4 935e00c0' in logs['live']
assert 'BOOT_STM submitted=46 produced=22' in logs['disabled']
assert 'BOOT_BOUNDARY pc=80212ff4 lr=80242240 msr=32' in logs['disabled']
assert 'PLAYRECORD_KERNEL_SEEK 0' in logs['live'] and 'PLAYRECORD_KERNEL_SEEK ' not in logs['disabled']
assert 'PLAYRECORD_SEEK_RETIRED' not in logs['live']
assert logs['live'].index('PLAYRECORD_SEEK_SUBMITTED') < logs['live'].index('PLAYRECORD_READ_RETIRED') < logs['live'].index('PLAYRECORD_KERNEL_SEEK 0')


def rows(log,prefix):
    found = [line for line in log.splitlines() if line.startswith(prefix)]
    assert found,prefix
    return found


def payload(prefix):
    found = rows(logs['live'],prefix)
    assert len(found) == 1
    return bytes(map(int,found[0][len(prefix):].split()))


observations = rows(logs['live'],'PLAYRECORD_SEEK_OBSERVE ')
assert len(observations) == 2
for kind,index in ((1,182),(2,183)):
    row = events[64 + index * 1280:64 + (index + 1) * 1280]
    actual = [int(value,16) for value in observations[kind - 1].split()[2:]]
    assert actual == [*struct.unpack_from('>2I',row,24),struct.unpack_from('>I',row,16)[0],
        struct.unpack_from('>I',row,768)[0],struct.unpack_from('>I',row,1056)[0],struct.unpack_from('>I',row,36)[0]]
    for tag,offset in (('CACHED',64),('PHYSICAL',128)):
        reply = bytearray(payload(f'PLAYRECORD_SEEK_REPLY_{tag} {kind} '))
        expected = row[offset:offset + 64]
        assert struct.unpack_from('>I',reply,24)[0] == 0x8053fd70
        assert struct.unpack_from('>I',expected,24)[0] == 0x8053ff90
        reply[24:28] = expected[24:28]
        assert reply == expected
for prefix in ('SC_COMPLETE_CONF_CACHED ','SC_COMPLETE_CONF_PHYSICAL ','SC_COMPLETE_PRODUCT_CACHED ',
    'SC_COMPLETE_PRODUCT_PHYSICAL ','ES_TICKET_CALLER_CACHED ','ES16_CALLER 2 ',
    'POST_ES16_CLOSE_CACHED ','POST_ES16_CLOSE_PHYSICAL ','BOOT_STM_ASYNC_CACHED ','BOOT_STM_ASYNC_PHYSICAL ',
    'INQUIRY_REPLY_CACHED ','INQUIRY_REPLY_PHYSICAL ','INQUIRY_DATA_CACHED ','INQUIRY_DATA_PHYSICAL ',
    'BOOT_STM_ASYNC dispatched=','PLAYRECORD_OPEN_CALLBACK ','PLAYRECORD_READ_CALLBACK ',
    'PLAYRECORD_READ_REPLY_CACHED ','PLAYRECORD_READ_REPLY_PHYSICAL ','PLAYRECORD_READ_DATA_CACHED ','PLAYRECORD_READ_DATA_PHYSICAL '):
    assert rows(logs['live'],prefix) == rows(logs['disabled'],prefix)
assert sha(lab) == seed_hash
(output / 'seek-audit.json').write_text(json.dumps({'result':'ACTUAL_SEEK0_ORIGINAL_CALLBACK_ENTRIES_MATCH_ALARM_DEC_BOUNDARY',
    'auditSha256':sha(Path(__file__)),'buildSha256':sha(output / 'build.json'),
    'liveLogSha256':sha(output / 'live-audit.log'),'disabledLogSha256':sha(output / 'disabled-audit.log'),
    'callbackOracleSha256':sha(capture_path),'seedSha256':seed_hash,
    'limits':['Existing kernel/FS returnsSEEK0 after original READ source retirement/head00C0; no forced SDK result/state.',
        'ISFS/Play entry args/MSR32/FD4/state3/head00C0 match original182/183;64x2 reply stack vector relocation FD70/FF90 explicitly retained.',
        'Play callback setsstate4/get1 then stops inside InsertAlarm before PPCMtdec SPR22. Callback return/work/packet free NOTcomplete.',
        'Processor/DEC guard and source policy unchanged; no skipped timer or synthetic callback completion.',
        'ACK64/reply-after-source-retirement is PC timing, not physical Wii/complete allocator/first screen.']},indent=2) + '\n')
print('PASS fresh SEEK0/READ source retirement/two original callback entries/full64 replies with explicit stack relocation/previous data-STM-seed; DEC alarm guard before SEEK retirement')

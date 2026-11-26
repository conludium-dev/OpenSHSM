"""Audit real READ128 and original callback/payload agreement before SEEK submission."""
from pathlib import Path
import base64
import hashlib
import json
import os
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
base = root / 'mass-fp-initializer-boot'
output = root / 'mass-playrecord-read-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
old = json.loads((base / 'build.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_playrecord_read_boot.py')
assert build['baseBuildSha256'] == sha(base / 'build.json')
assert build['executableSha256'] == sha(output / 'openshsm-mass-boot')
for path,digest in {**build['sourceHashes'],**build['headerHashes']}.items():
    assert sha(Path(path)) == digest
for name in ('playrecord_read_dispatch.h','playrecord_read_flush.h'):
    assert (output / name).read_bytes() == (experiment / name).read_bytes()
assert len(build['records']) == len(old['records']) == 125
rebuilt = ('output_62.cpp','output_63.cpp','output_64.cpp','output_67.cpp','output_68.cpp')
for row,prior in zip(build['records'],old['records']):
    assert row['file'] == prior['file']
    expected = Path(prior['source']).read_text()
    if row['file'] == 'output_67.cpp':
        expected = expected.replace('loc_80240680: ;','loc_80240680: ;\n    nwii::runtime::experiment_playrecord_read_observe(ctx,1);')
    if row['file'] == 'output_64.cpp':
        expected = expected.replace('loc_8021CDE0: ;','loc_8021CDE0: ;\n    nwii::runtime::experiment_playrecord_read_observe(ctx,2);')
    assert Path(row['source']).read_text() == expected
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    if row['file'] not in rebuilt:
        assert row == prior
for name in ('fs_device.cpp','stm_device.cpp','di_device.cpp','es_device.cpp','ni_guard.h','fp32_transfer.h','fsubs_integer_bias.h'):
    assert (output / name).read_bytes() == (base / name).read_bytes()
capture_path = root / 'dolphin-playrecord-events-disc/fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
events = base64.b64decode(capture['events'])
lab = root / 'playrecord-fs-device/pc-owned-playrecord.bin'
seed = lab.read_bytes()
assert seed == base64.b64decode(capture['playrecordLabFile']) and len(seed) == 128
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
        env['SHSM_PLAYRECORD_READ_DISABLED'] = '1'
    result = subprocess.run([str(output / 'openshsm-mass-boot'),'work/private-game/disc/DATA/sys/main.dol',
        str(output / 'boot-quarantine.tsv'),str(root / 'sram-native/settings.bin')],
        env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode == 7 and not result.stderr
    logs[mode] = result.stdout
    (output / (mode + '-audit.log')).write_text(result.stdout)
assert 'BOOT_BOUNDARY pc=80212ff4 lr=80242240 msr=32' in logs['live']
assert 'BOOT_STM submitted=46 produced=22' in logs['live']
assert 'BOOT_STM submitted=44 produced=21' in logs['disabled']
assert 'PLAYRECORD_NEXT_STATE 935e00a0 1 3 1 4 935e0120' in logs['live']
assert 'PLAYRECORD_KERNEL_READ ' not in logs['disabled']
order = ['PLAYRECORD_READ_SUBMITTED','PLAYRECORD_OPEN_RETIRED','PLAYRECORD_KERNEL_READ 128',
    'PLAYRECORD_READ_CALLBACK 1','PLAYRECORD_READ_CALLBACK 2']
positions = [logs['live'].index(tag) for tag in order]
assert positions == sorted(positions)


def rows(log,prefix):
    found = [line for line in log.splitlines() if line.startswith(prefix)]
    assert found,prefix
    return found


def payload(prefix):
    found = rows(logs['live'],prefix)
    assert len(found) == 1
    return bytes(map(int,found[0][len(prefix):].split()))


for kind,index in ((1,171),(2,172)):
    row = events[64 + index * 1280:64 + (index + 1) * 1280]
    fields = rows(logs['live'],f'PLAYRECORD_READ_CALLBACK {kind} ')[0].split()[2:]
    actual = [int(value,16) for value in fields]
    assert actual == [*struct.unpack_from('>2I',row,24),struct.unpack_from('>I',row,16)[0],
        struct.unpack_from('>I',row,768)[0],struct.unpack_from('>I',row,1056)[0],struct.unpack_from('>I',row,36)[0]]
    assert payload(f'PLAYRECORD_READ_REPLY_CACHED {kind} ') == row[192:256]
    assert payload(f'PLAYRECORD_READ_REPLY_PHYSICAL {kind} ') == row[256:320]
    assert payload(f'PLAYRECORD_READ_DATA_CACHED {kind} ') == payload(f'PLAYRECORD_READ_DATA_PHYSICAL {kind} ') == row[640:768] == seed
next_row = events[64 + 173 * 1280:64 + 174 * 1280]
for prefix,offset in (('PLAYRECORD_NEXT_CACHED ',64),('PLAYRECORD_NEXT_PHYSICAL ',128)):
    actual = bytearray(payload(prefix))
    expected = next_row[offset:offset + 64]
    assert struct.unpack_from('>I',actual,24)[0] == 0x8053fd70
    assert struct.unpack_from('>I',expected,24)[0] == 0x8053ff90
    actual[24:28] = expected[24:28]
    assert actual == expected
for prefix in ('SC_COMPLETE_CONF_CACHED ','SC_COMPLETE_CONF_PHYSICAL ','SC_COMPLETE_PRODUCT_CACHED ',
    'SC_COMPLETE_PRODUCT_PHYSICAL ','ES_TICKET_CALLER_CACHED ','ES16_CALLER 2 ',
    'POST_ES16_CLOSE_CACHED ','POST_ES16_CLOSE_PHYSICAL ','BOOT_STM_ASYNC_CACHED ','BOOT_STM_ASYNC_PHYSICAL ',
    'INQUIRY_REPLY_CACHED ','INQUIRY_REPLY_PHYSICAL ','INQUIRY_DATA_CACHED ','INQUIRY_DATA_PHYSICAL ',
    'BOOT_STM_ASYNC dispatched=','PLAYRECORD_OPEN_CALLBACK '):
    assert rows(logs['live'],prefix) == rows(logs['disabled'],prefix)
assert sha(lab) == seed_hash
(output / 'read-audit.json').write_text(json.dumps({'result':'NATIVE_READ128_ORIGINAL_CALLBACKS_FULL_REPLY_DATA_MATCH_SEEK_PREP',
    'auditSha256':sha(Path(__file__)),'buildSha256':sha(output / 'build.json'),
    'captureSha256':sha(capture_path),'liveLogSha256':sha(output / 'live-audit.log'),
    'disabledLogSha256':sha(output / 'disabled-audit.log'),'seedSha256':seed_hash,
    'limits':['Existing FS/kernel actual READ128; submission before source OPEN retirement then READ delivery/callbacks matches original ordering.',
        'Two callbacks args/MSR32/FD4/state2/free0060/full64x2 replies/full128x2 payloads match original171/172.',
        'Source state3/get1 prepares SEEK0 before READ work/packet free; ignored vectorFD70 vsFF90 is explicit stack relocation.',
        'ACK64/reply poll after source retirement is PC timing, not physical IOS/cache cycle accuracy.',
        'Seed already all zero before READ: no claimed data transition; WRITE/CLOSE/SEEK execution and first screen unverified.']},indent=2) + '\n')
print('PASS fresh native READ128/two original callbacks/full64x2 reply and128x2 data/order/previous buffers-STM-seed; next SEEK before submission')

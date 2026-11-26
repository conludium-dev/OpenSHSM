"""Verify original path/packet flush to sender without file OPEN or writes."""
from pathlib import Path
import hashlib
import json
import os
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
base = root / 'mass-es-close-after-consumption-boot'
output = root / 'mass-playrecord-open-flush-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3',str(experiment/'verify_post_es16_close_open.py')],check=True)
build = json.loads((output/'build.json').read_text())
old_build = json.loads((base/'build.json').read_text())
assert build['builderSha256'] == sha(experiment/'build_playrecord_open_flush_boot.py')
assert build['executableSha256'] == sha(output/'openshsm-mass-boot')
for path,digest in {**build['sourceHashes'],**build['headerHashes']}.items():
    assert sha(Path(path)) == digest
assert (output/'playrecord_open_flush.h').read_bytes() == (experiment/'playrecord_open_flush.h').read_bytes()
assert len(build['records']) == len(old_build['records']) == 125
for row,old in zip(build['records'],old_build['records']):
    assert row['file'] == old['file'] and row['sourceSha256'] == old['sourceSha256']
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    if row['file'] not in ('output_62.cpp','output_63.cpp','output_67.cpp'):
        assert row['object'] == old['object']
expected = (base/'flush_syscall.h').read_text().replace('#include "es_consumption_flush.h"',
    '#include "es_consumption_flush.h"\n#include "playrecord_open_flush.h"').replace(
    '!experiment_es_consumption_flush(context))','!experiment_es_consumption_flush(context) && !experiment_playrecord_open_flush(context))')
assert (output/'flush_syscall.h').read_text() == expected
for name in ('ipc_ack_frontend.h','si_external_delivery.h','boot-wrapper.cpp','fs_device.cpp','es_device.cpp','di_device.cpp','stm_device.cpp'):
    assert (output/name).read_bytes() == (base/name).read_bytes()
lab = Path('_scratch/tmp/dolphin-es-close-after-consumption-disc-user/Wii/title/00000001/00000002/data/play_rec.dat')
lab_before = sha(lab)
logs = {}
for mode in ('live','disabled'):
    env = {key:value for key,value in os.environ.items() if not key.startswith('SHSM_')}
    env.update(SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin',SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin',
        SHSM_ES_LAB_CONSUMPTION='1',SHSM_DI_LAB_INQUIRY_PATH=str(root/'di-inquiry-device/dolphin-lab-inquiry.bin'),
        SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF',
        SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')
    if mode == 'disabled':
        env['SHSM_PLAYRECORD_FLUSH_DISABLED'] = '1'
    result = subprocess.run([str(output/'openshsm-mass-boot'),'work/private-game/disc/DATA/sys/main.dol',
        str(output/'boot-quarantine.tsv'),str(root/'sram-native/settings.bin')],env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode == 7 and not result.stderr
    logs[mode] = result.stdout
    (output/(mode+'-audit.log')).write_text(result.stdout)
live,disabled = logs['live'],logs['disabled']
assert 'BOOT_BOUNDARY pc=80241c30 lr=80242384 msr=2032' in live
assert 'BOOT_BOUNDARY pc=80212ff4 lr=8024250c msr=a032' in disabled
for log in logs.values():
    assert 'BOOT_STM submitted=42 produced=20' in log
    assert 'POST_ES16_CLOSE_SOURCE 2 0 a032 ffffffff 935e0060' in log

def payload(log,prefix):
    matches = [line[len(prefix):] for line in log.splitlines() if line.startswith(prefix)]
    assert len(matches) == 1,prefix
    return bytes(map(int,matches[0].split()))

header = struct.pack('>8I',1,0,0,0x135e1020,3,2,0x8053fd70,0)
assert payload(live,'PLAYRECORD_PRE_SEND_CACHED ') == header + struct.pack('>2I',0x80240680,0x935e1020) + bytes(24)
assert payload(live,'PLAYRECORD_PRE_SEND_PHYSICAL ') == header + bytes(32)
for prefix,size in [('SC_COMPLETE_CONF_CACHED ',16384),('SC_COMPLETE_CONF_PHYSICAL ',16384),
    ('SC_COMPLETE_PRODUCT_CACHED ',256),('SC_COMPLETE_PRODUCT_PHYSICAL ',256),('ES_TICKET_CALLER_CACHED ',216),
    ('ES16_CALLER 2 ',4),('POST_ES16_CLOSE_CACHED ',64),('POST_ES16_CLOSE_PHYSICAL ',64),
    ('BOOT_STM_ASYNC_CACHED ',64),('BOOT_STM_ASYNC_PHYSICAL ',64)]:
    assert len(payload(live,prefix)) == size and payload(live,prefix) == payload(disabled,prefix)
for kind in range(1,5):
    for tag in ('INQUIRY_REPLY_CACHED ','INQUIRY_REPLY_PHYSICAL ','INQUIRY_DATA_CACHED ','INQUIRY_DATA_PHYSICAL '):
        prefix = tag+str(kind)+' '
        assert payload(live,prefix) == payload(disabled,prefix)
assert sha(lab) == lab_before and lab.stat().st_size == 128
proof = json.loads((root/'playrecord-source/ghidra/verification.json').read_text())
assert [(row['instructions'],row['bytes']) for row in proof['records']] == [(21,84),(301,1204)]
(output/'flush-audit.json').write_text(json.dumps({'result':'ORIGINAL_PLAYRECORD_OPEN_PATH_PACKET_FLUSH_TO_SENDER_PASS',
    'auditSha256':sha(Path(__file__)),'buildSha256':sha(output/'build.json'),
    'liveLogSha256':sha(output/'live-audit.log'),'disabledLogSha256':sha(output/'disabled-audit.log'),
    'labFileSha256':lab_before,'limits':['All125 PPC sources unchanged,three objects rebuilt122 retained.',
        'Only one exact path-flush guard added; original SDK normalizes path/mode and commits header32; callback/user tail stays cached-only.',
        'Service still refuses mode3 play-record OPEN; native request not submitted/read/written or callbacks completed.',
        'Current Ghidra C has unresolved SDA/indirect jump warnings; not a semantic execution oracle.',
        'Previous full data/pendingSTM and original LAB file128 unchanged; no first screen/fullgame claim.']},indent=2)+'\n')
print('PASS fresh original play-record flush-to-sender/header32 coherent/cached-only callback tail/previous buffers/LAB128 unchanged; OPEN not submitted')

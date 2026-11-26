"""Audit real DEC admission and original SEEK return/free completion."""
from pathlib import Path
import base64
import hashlib
import json
import os
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
base = root / 'mass-playrecord-seek-boot'
output = root / 'mass-playrecord-dec-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3',str(experiment / 'verify_dec_clock_component.py')],check=True)
build = json.loads((output / 'build.json').read_text())
old = json.loads((base / 'build.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_playrecord_dec_boot.py')
assert build['baseBuildSha256'] == sha(base / 'build.json')
assert build['executableSha256'] == sha(output / 'openshsm-mass-boot')
for path,digest in {**build['sourceHashes'],**build['headerHashes']}.items():
    assert sha(Path(path)) == digest
assert len(build['records']) == len(old['records']) == 125
for row,prior in zip(build['records'],old['records']):
    assert row['file'] == prior['file']
    expected = Path(prior['source']).read_text()
    if row['file'] == 'output_63.cpp':
        expected = expected.replace('    ctx.write_dec(ctx.gpr[3]); // mtdec r3','    nwii::runtime::experiment_playrecord_dec_write(ctx,ctx.gpr[3]);')
    assert Path(row['source']).read_text() == expected
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    assert Path(row['source']).parent == output and Path(row['object']).parent == output
    assert row['object'] != prior['object']
assert (output / 'timebase_adapter.h').read_bytes() == (root / 'dec-clock-component/timebase_adapter.h').read_bytes()
for name in ('dec_clock_adapter.h','playrecord_dec_adapter.h'):
    assert (output / name).read_bytes() == (experiment / name).read_bytes()
assert (output / 'boot-quarantine.tsv').read_text() == (base / 'boot-quarantine.tsv').read_text().replace(
    '802106E0\tUNVERIFIED_PROCESSOR_REGISTER_22\n','')
for name in ('boot-wrapper.cpp','mass_boot.cpp','fs_device.cpp','stm_device.cpp','di_device.cpp','es_device.cpp','boot_poll.h','si_external_delivery.h'):
    assert (output / name).read_bytes() == (base / name).read_bytes()
capture_path = root / 'dolphin-playrecord-dec-events-disc/fpr-init-true-dolphin.json'
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
        env['SHSM_PLAYRECORD_DEC_DISABLED'] = '1'
    result = subprocess.run([str(output / 'openshsm-mass-boot'),'work/private-game/disc/DATA/sys/main.dol',
        str(output / 'boot-quarantine.tsv'),str(root / 'sram-native/settings.bin')],
        env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode == 7 and not result.stderr
    logs[mode] = result.stdout
    (output / (mode + '-audit.log')).write_text(result.stdout)
assert 'BOOT_BOUNDARY pc=80015234 lr=8021e8f4 msr=a032' in logs['live']
assert 'address=8001526c opcode=ec000828' in logs['live']
assert 'BOOT_BOUNDARY pc=802106e0 lr=80212078 msr=32' in logs['disabled']
for log in logs.values():
    assert 'BOOT_STM submitted=48 produced=23' in log
assert 'PLAYRECORD_SEEK_RETIRED' in logs['live'] and 'PLAYRECORD_SEEK_RETIRED' not in logs['disabled']
assert 'PLAYRECORD_SEEK_END_STATE  4 1 0 0 0 0 0 4 935e0060' in logs['live']


def rows(log,prefix):
    found = [line for line in log.splitlines() if line.startswith(prefix)]
    assert found,prefix
    return found


dec = rows(logs['live'],'PLAYRECORD_DEC_PROGRAMMED ')[0].split()[1:]
assert int(dec[0],16) == 0x7fffffff and list(map(int,dec[2:])) == [0,1]
native = rows(logs['live'],'PLAYRECORD_SEEK_OBSERVE ')
assert len(native) == 5
for line,index in zip(native,(182,183,186,187,189)):
    row = events[64 + index * 1280:64 + (index + 1) * 1280]
    actual = [int(value,16) for value in line.split()[2:]]
    assert actual == [*struct.unpack_from('>2I',row,24),struct.unpack_from('>I',row,16)[0],
        struct.unpack_from('>I',row,768)[0],struct.unpack_from('>I',row,1056)[0],struct.unpack_from('>I',row,36)[0]]
assert logs['live'].index('PLAYRECORD_DEC_PROGRAMMED ') < logs['live'].index('PLAYRECORD_SEEK_OBSERVE 3 ') < logs['live'].index('PLAYRECORD_SEEK_RETIRED')
for prefix in ('SC_COMPLETE_CONF_CACHED ','SC_COMPLETE_CONF_PHYSICAL ','SC_COMPLETE_PRODUCT_CACHED ',
    'SC_COMPLETE_PRODUCT_PHYSICAL ','ES_TICKET_CALLER_CACHED ','ES16_CALLER 2 ',
    'POST_ES16_CLOSE_CACHED ','POST_ES16_CLOSE_PHYSICAL ','BOOT_STM_ASYNC_CACHED ','BOOT_STM_ASYNC_PHYSICAL ',
    'INQUIRY_REPLY_CACHED ','INQUIRY_REPLY_PHYSICAL ','INQUIRY_DATA_CACHED ','INQUIRY_DATA_PHYSICAL ',
    'BOOT_STM_ASYNC dispatched=','PLAYRECORD_READ_CALLBACK ','PLAYRECORD_READ_REPLY_CACHED ',
    'PLAYRECORD_READ_REPLY_PHYSICAL ','PLAYRECORD_READ_DATA_CACHED ','PLAYRECORD_READ_DATA_PHYSICAL ',
    'PLAYRECORD_SEEK_REPLY_CACHED ','PLAYRECORD_SEEK_REPLY_PHYSICAL '):
    if prefix in ('SC_COMPLETE_CONF_PHYSICAL ','BOOT_STM_ASYNC_PHYSICAL '):
        cached_prefix = prefix.replace('PHYSICAL','CACHED')
        live = bytes(map(int,rows(logs['live'],prefix)[0].split()[1:]))
        disabled = bytes(map(int,rows(logs['disabled'],prefix)[0].split()[1:]))
        cached = bytes(map(int,rows(logs['live'],cached_prefix)[0].split()[1:]))
        assert rows(logs['live'],cached_prefix) == rows(logs['disabled'],cached_prefix)
        assert live == cached
        if prefix == 'SC_COMPLETE_CONF_PHYSICAL ':
            assert len(live) == 16384 and live[:16288] == disabled[:16288]
            assert disabled[16288:] == bytes(92) + b'SCed'
        else:
            assert len(live) == 64 and live[:32] == disabled[:32]
            assert disabled[32:] == bytes(32)
            assert live[32:] == bytes.fromhex('8021cc70') + bytes(28)
    else:
        assert rows(logs['live'],prefix) == rows(logs['disabled'],prefix),prefix
assert sha(lab) == seed_hash
(output / 'dec-boot-audit.json').write_text(json.dumps({'result':'NATIVE_DEC_ARMED_ORIGINAL_SEEK_CALLBACK_FREE_RETURN_COMPLETE',
    'auditSha256':sha(Path(__file__)),'buildSha256':sha(output / 'build.json'),
    'liveLogSha256':sha(output / 'live-audit.log'),'disabledLogSha256':sha(output / 'disabled-audit.log'),
    'oracleCaptureSha256':sha(capture_path),'seedSha256':seed_hash,
    'limits':['All125 objects rebuilt for ClockContext ABI; only output63 original mtdec body replaced.',
        'Native positive DEC uses existing clock/counter/EventScheduler, future timer armed without pending interrupt.',
        'Original SEEK callback return/workfree/packetfree match186/187/189; final state4/get1/FD4/head0060.',
        'Expiry model tested, but original negative writes/underflow IRQ/DEC exception delivery remain guarded.',
        'Logical cached SC/STM data unchanged; physical SC last96 and STM callback tail become equal to cached data. Cache eviction/writeback is inferred from the existing memory frontend, not original hardware timing proof.',
        'Next actual native boundary is another static initializer fsubs, not first screen/full game.']},indent=2) + '\n')
print('PASS fresh native DEC armed/SEEK original return-workfree-packetfree/state4-get1-head0060/all125 rebuilt/previous data-STM-seed; next initializer fsubs')

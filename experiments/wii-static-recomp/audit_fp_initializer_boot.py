"""Audit exact source arithmetic, actual OPEN callbacks and guarded READ preparation."""
from pathlib import Path
import base64
import hashlib
import json
import os
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
base = root / 'mass-fp32-playrecord-boot'
output = root / 'mass-fp-initializer-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3',str(experiment / 'verify_fp_initializer_native.py')],check=True)
build = json.loads((output / 'build.json').read_text())
old = json.loads((base / 'build.json').read_text())
assert build['baseBuildSha256'] == sha(base / 'build.json')
assert len(build['records']) == len(old['records']) == 125
for row,prior in zip(build['records'],old['records']):
    assert row['file'] == prior['file']
    if row['file'] != 'output_1.cpp':
        assert row == prior
        continue
    expected = Path(prior['source']).read_text().replace(
        '    nwii::runtime::experiment_ni_guard(ctx, 0xec000828, 0x8000c31c);\n    ctx.fpr[0] = (float)(ctx.fpr[0] - ctx.fpr[1]); // fsubs',
        '    nwii::runtime::experiment_fsubs_integer_bias(ctx, 0xec000828);').replace(
        'loc_8000C328: ;','loc_8000C328: ;\n    if (ctx.msr == 0xa032 && nwii::runtime::stmSubmitted == 44) { std::cout << "FP_INITIALIZER_SOURCE " << std::hex << ctx.fpscr << " " << nwii::runtime::bat_memory_read32(ctx,0x80529158) << " " << nwii::runtime::bat_memory_read32(ctx,0x8052915c) << std::dec << std::endl; }')
    assert expected == Path(row['source']).read_text()
for name in ('ni_guard.h','fp32_transfer.h','flush_syscall.h','si_external_delivery.h','playrecord_open_dispatch.h',
    'fs_device.cpp','es_device.cpp','di_device.cpp','stm_device.cpp'):
    assert (output / name).read_bytes() == (base / name).read_bytes()
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
        env['SHSM_FP_INITIALIZER_DISABLED'] = '1'
    result = subprocess.run([str(output / 'openshsm-mass-boot'),'work/private-game/disc/DATA/sys/main.dol',
        str(output / 'boot-quarantine.tsv'),str(root / 'sram-native/settings.bin')],
        env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode == 7 and not result.stderr
    logs[mode] = result.stdout
    (output / (mode + '-audit.log')).write_text(result.stdout)
assert 'BOOT_BOUNDARY pc=80212ff4 lr=80242240 msr=32' in logs['live']
assert 'BOOT_STM submitted=44 produced=21' in logs['live']
assert 'FP_INITIALIZER_SOURCE 4004 44040000 210' in logs['live']
assert 'PLAYRECORD_KERNEL_OPEN 4' in logs['live']
assert 'PLAYRECORD_READ_PREP_STATE 935e0100 1 2 4 935e0120' in logs['live']
assert 'BOOT_BOUNDARY pc=8000c2f4 lr=8021e8f4 msr=a032' in logs['disabled']
assert 'BOOT_STM submitted=44 produced=20' in logs['disabled']
assert 'PLAYRECORD_KERNEL_OPEN ' not in logs['disabled']
capture_path = root / 'dolphin-playrecord-events-disc/fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
raw = base64.b64decode(capture['events'])
callbacks = [line.split()[1:] for line in logs['live'].splitlines() if line.startswith('PLAYRECORD_OPEN_CALLBACK ')]
assert len(callbacks) == 3
for index,fields in zip((159,160,161),callbacks):
    row = raw[64 + index * 1280:64 + (index + 1) * 1280]
    actual = list(map(lambda value:int(value,16),fields))
    r3,r4 = struct.unpack_from('>2I',row,24)
    msr = struct.unpack_from('>I',row,16)[0]
    fd = struct.unpack_from('>I',row,768)[0]
    state = struct.unpack_from('>I',row,1056)[0]
    head = struct.unpack_from('>I',row,36)[0]
    assert actual == [index - 158,r3,r4,msr,fd,state,head]


def rows(log,prefix):
    found = [line for line in log.splitlines() if line.startswith(prefix)]
    assert found,prefix
    return found


def payload(prefix):
    found = rows(logs['live'],prefix)
    assert len(found) == 1
    return bytes(map(int,found[0][len(prefix):].split()))


read = raw[64 + 162 * 1280:64 + 163 * 1280]
assert payload('PLAYRECORD_READ_PREP_CACHED ') == read[192:256]
assert payload('PLAYRECORD_READ_PREP_PHYSICAL ') == read[256:320]
for prefix in ('SC_COMPLETE_CONF_CACHED ','SC_COMPLETE_CONF_PHYSICAL ','SC_COMPLETE_PRODUCT_CACHED ',
    'SC_COMPLETE_PRODUCT_PHYSICAL ','ES_TICKET_CALLER_CACHED ','ES16_CALLER 2 ',
    'POST_ES16_CLOSE_CACHED ','POST_ES16_CLOSE_PHYSICAL ','BOOT_STM_ASYNC_CACHED ','BOOT_STM_ASYNC_PHYSICAL ',
    'INQUIRY_REPLY_CACHED ','INQUIRY_REPLY_PHYSICAL ','INQUIRY_DATA_CACHED ','INQUIRY_DATA_PHYSICAL ',
    'BOOT_STM_ASYNC dispatched='):
    assert rows(logs['live'],prefix) == rows(logs['disabled'],prefix)
assert sha(lab) == seed_hash
(output / 'initializer-boot-audit.json').write_text(json.dumps({
    'result':'WHOLE_VERIFIED_INITIALIZER_NATIVE_OPEN_CALLBACKS_ORIGINAL_MATCH_READ_PREP',
    'auditSha256':sha(Path(__file__)),'buildSha256':sha(output / 'build.json'),
    'liveLogSha256':sha(output / 'live-audit.log'),'disabledLogSha256':sha(output / 'disabled-audit.log'),
    'callbackOracleSha256':sha(capture_path),'seedSha256':seed_hash,
    'limits':['One object rebuilt124 retained; one source arithmetic replacement plus read-only return observation.',
        'Native source initializer528/FPSCR4004, real kernelOPEN4 and original ISFS/NAND/Play callbacks match original three events.',
        'Read request preparation64cached+64physical matches original event162; source state2/freeheap0120, BEFORE callback/work/packet retirement.',
        'READ not submitted: guarded flush12FF4/LR42240/MSR32. No read/seek/free completion or first screen.',
        'Measured signed-int bias arithmetic only; no general fsubs or physical Wii proof.']},indent=2) + '\n')
print('PASS fresh whole initializer/native OPEN4/three original callbacks/exact64 READ-prep views/previous buffers-STM-seed; READ still before submission')

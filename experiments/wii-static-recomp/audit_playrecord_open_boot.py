"""Audit submitted OPEN and the genuine next FP boundary without claiming completion."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
base = root / 'mass-playrecord-open-flush-boot'
output = root / 'mass-playrecord-open-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
old_build = json.loads((base / 'build.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_playrecord_open_boot.py')
assert build['executableSha256'] == sha(output / 'openshsm-mass-boot')
assert build['baseBuildSha256'] == sha(base / 'build.json')
assert build['playrecordDevicePreparationSha256'] == sha(root / 'playrecord-fs-device/preparation.json')
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
assert (output / 'playrecord_open_dispatch.h').read_bytes() == (experiment / 'playrecord_open_dispatch.h').read_bytes()
assert (output / 'fs_device.cpp').read_bytes() == (root / 'playrecord-fs-device/fs_device.cpp').read_bytes()
changed = ('output_62.cpp','output_64.cpp','output_67.cpp','output_68.cpp')
assert len(build['records']) == len(old_build['records']) == 125
for row, old in zip(build['records'],old_build['records']):
    assert row['file'] == old['file']
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    expected = Path(old['source']).read_text()
    if row['file'] == 'output_67.cpp':
        expected = expected.replace('loc_80240680: ;','loc_80240680: ;\n    nwii::runtime::experiment_playrecord_callback_observe(ctx, 1);')
    if row['file'] == 'output_68.cpp':
        expected = expected.replace('loc_80244E30: ;','loc_80244E30: ;\n    nwii::runtime::experiment_playrecord_callback_observe(ctx, 2);')
    if row['file'] == 'output_64.cpp':
        expected = expected.replace('loc_8021CDE0: ;','loc_8021CDE0: ;\n    nwii::runtime::experiment_playrecord_callback_observe(ctx, 3);')
    assert Path(row['source']).read_text() == expected
    if row['file'] not in changed:
        assert row['object'] == old['object']
for name in ('ni_guard.h','frsp_adapter.h','flush_syscall.h','es_device.cpp','di_device.cpp','stm_device.cpp'):
    assert (output / name).read_bytes() == (base / name).read_bytes()
lab = root / 'playrecord-fs-device/pc-owned-playrecord.bin'
original_lab = Path('_scratch/tmp/dolphin-playrecord-events-disc-user/Wii/title/00000001/00000002/data/play_rec.dat')
before = {str(path):sha(path) for path in (lab,original_lab)}
logs = {}
for mode in ('live','disabled'):
    env = {key:value for key,value in os.environ.items() if not key.startswith('SHSM_')}
    env.update(SHSM_PLAYRECORD_LAB_FILE=str(lab),SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin',
        SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin',SHSM_ES_LAB_CONSUMPTION='1',
        SHSM_DI_LAB_INQUIRY_PATH=str(root / 'di-inquiry-device/dolphin-lab-inquiry.bin'),
        SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF',
        SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')
    if mode == 'disabled':
        env['SHSM_PLAYRECORD_OPEN_DISABLED'] = '1'
    result = subprocess.run([str(output / 'openshsm-mass-boot'),'work/private-game/disc/DATA/sys/main.dol',
        str(output / 'boot-quarantine.tsv'),str(root / 'sram-native/settings.bin')],
        env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode == 7 and not result.stderr
    logs[mode] = result.stdout
    (output / (mode + '-audit.log')).write_text(result.stdout)
assert 'BOOT_BOUNDARY pc=80006b20 lr=80006b20 msr=a032' in logs['live']
assert 'NI unsupported FP before instruction address=80006b20 opcode=c0028020' in logs['live']
assert 'BOOT_STM submitted=44 produced=20' in logs['live']
assert 'BOOT_BOUNDARY pc=80241c30 lr=80242384 msr=2032' in logs['disabled']
assert 'BOOT_STM submitted=42 produced=20' in logs['disabled']
for log in logs.values():
    assert 'PLAYRECORD_KERNEL_OPEN ' not in log and 'PLAYRECORD_OPEN_CALLBACK ' not in log
    assert 'POST_ES16_CLOSE_SOURCE 2 0 a032 ffffffff 935e0060' in log


def lines(log,prefix):
    found = [line for line in log.splitlines() if line.startswith(prefix)]
    assert found, prefix
    return found


for prefix in ('SC_COMPLETE_CONF_CACHED ','SC_COMPLETE_CONF_PHYSICAL ','SC_COMPLETE_PRODUCT_CACHED ',
    'SC_COMPLETE_PRODUCT_PHYSICAL ','ES_TICKET_CALLER_CACHED ','ES16_CALLER 2 ',
    'POST_ES16_CLOSE_CACHED ','POST_ES16_CLOSE_PHYSICAL ','BOOT_STM_ASYNC_CACHED ','BOOT_STM_ASYNC_PHYSICAL ',
    'INQUIRY_REPLY_CACHED ','INQUIRY_REPLY_PHYSICAL ','INQUIRY_DATA_CACHED ','INQUIRY_DATA_PHYSICAL ',
    'BOOT_STM_ASYNC dispatched='):
    assert lines(logs['live'],prefix) == lines(logs['disabled'],prefix)
assert before == {str(path):sha(path) for path in (lab,original_lab)}
(output / 'open-submission-audit.json').write_text(json.dumps({
    'result':'ORIGINAL_OPEN_SUBMITTED_ACK_PATH_REACHES_UNSUPPORTED_NI_LFS_BOUNDARY',
    'auditSha256':sha(Path(__file__)), 'buildSha256':sha(output / 'build.json'),
    'liveLogSha256':sha(output / 'live-audit.log'), 'disabledLogSha256':sha(output / 'disabled-audit.log'),
    'seedHashes':before,
    'limits':['44 stores/20 completed productions: new OPEN submitted, not yet serviced/replied/callback-completed.',
        'After submission, startup reaches original global-constructor fn80006A28 lfs c0028020 at80006B20 with FPSCR NI; guard preserved, no state normalization.',
        'Four objects rebuilt121 retained; three sources have only exact read-only callback observation inserts.',
        'Full previous buffers/pending STM/PC-owned and original LAB seeds preserved; no first screen.']},indent=2) + '\n')
print('PASS fresh OPEN submission44/20 vs disabled42/20/unchanged NI guard/previous buffers/seed hashes; actual next NI-lfs boundary, not OPEN completion')

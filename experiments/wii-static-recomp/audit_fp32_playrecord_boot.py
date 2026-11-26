"""Reproduce FP32 lowering and audit the actual continuation, not whole-game success."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
from fp32_lowering import lower

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
base = root / 'mass-playrecord-open-boot'
output = root / 'mass-fp32-playrecord-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
old = json.loads((base / 'build.json').read_text())
lowering_path = output / 'lowering.json'
lowering = json.loads(lowering_path.read_text())
assert build['builderSha256'] == sha(experiment / 'build_fp32_playrecord_boot.py')
assert build['baseBuildSha256'] == sha(base / 'build.json')
assert build['executableSha256'] == sha(output / 'openshsm-mass-boot')
assert lowering['lowererSha256'] == sha(experiment / 'fp32_lowering.py')
assert lowering['proofSha256'] == sha(root / 'dolphin-fp32/comparison.json')
for path,digest in {**build['sourceHashes'],**build['headerHashes']}.items():
    assert sha(Path(path)) == digest
assert (output / 'fp32_transfer.h').read_bytes() == (experiment / 'fp32_transfer.h').read_bytes()
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert len(build['records']) == len(old['records']) == 125
rebuilt, sites = 0, 0
for row,prior in zip(build['records'],old['records']):
    assert row['file'] == prior['file']
    expected,changes = lower(Path(prior['source']).read_text(),dol)
    assert Path(row['source']).read_text() == expected
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    if changes:
        assert lowering['changes'][row['file']] == changes
        assert row['source'] != prior['source'] and row['object'] != prior['object']
        rebuilt += 1
        sites += len(changes)
    else:
        assert row == prior
assert rebuilt == len(lowering['changes'])
for name in ('boot-wrapper.cpp','fs_device.cpp','es_device.cpp','di_device.cpp','stm_device.cpp',
    'ni_guard.h','flush_syscall.h','si_external_delivery.h','playrecord_open_dispatch.h'):
    assert (output / name).read_bytes() == (base / name).read_bytes()
assert (output / 'ipc_ack_frontend.h').read_text() == (base / 'ipc_ack_frontend.h').read_text().replace(
    '#include "playrecord_open_dispatch.h"','#include "playrecord_open_dispatch.h"\n#include "fp32_transfer.h"')
lab = root / 'playrecord-fs-device/pc-owned-playrecord.bin'
lab_hash = sha(lab)
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
assert 'NI unsupported FP before instruction address=80006b20' not in logs['live']
assert 'BOOT_BOUNDARY pc=80241c30 lr=80242384 msr=2032' in logs['disabled']
assert 'BOOT_STM submitted=42 produced=20' in logs['disabled']


def lines(log,prefix):
    rows = [line for line in log.splitlines() if line.startswith(prefix)]
    assert rows, prefix
    return rows


for prefix in ('SC_COMPLETE_CONF_CACHED ','SC_COMPLETE_CONF_PHYSICAL ','SC_COMPLETE_PRODUCT_CACHED ',
    'SC_COMPLETE_PRODUCT_PHYSICAL ','ES_TICKET_CALLER_CACHED ','ES16_CALLER 2 ',
    'POST_ES16_CLOSE_CACHED ','POST_ES16_CLOSE_PHYSICAL ','BOOT_STM_ASYNC_CACHED ','BOOT_STM_ASYNC_PHYSICAL ',
    'INQUIRY_REPLY_CACHED ','INQUIRY_REPLY_PHYSICAL ','INQUIRY_DATA_CACHED ','INQUIRY_DATA_PHYSICAL ',
    'BOOT_STM_ASYNC dispatched='):
    assert lines(logs['live'],prefix) == lines(logs['disabled'],prefix)
assert sha(lab) == lab_hash
boundary = lines(logs['live'],'BOOT_BOUNDARY ')[0]
assert boundary != lines((base / 'live-audit.log').read_text(),'BOOT_BOUNDARY ')[0]
(output / 'continuation-audit.json').write_text(json.dumps({
    'result':'VERIFIED_FP32_MODULE_CONTINUES_PAST_ORIGINAL_CONSTRUCTOR_LOAD',
    'auditSha256':sha(Path(__file__)),'buildSha256':sha(output / 'build.json'),
    'loweringSha256':sha(lowering_path),'liveLogSha256':sha(output / 'live-audit.log'),
    'disabledLogSha256':sha(output / 'disabled-audit.log'),'boundary':boundary,
    'rebuiltObjects':rebuilt,'retainedObjects':125 - rebuilt,'sites':sites,'seedSha256':lab_hash,
    'limits':['All changed instruction bodies independently reproduced against own DOL and original192-case proof.',
        'Exact-single stores only; other NI/code-write/IRQ/file guards preserved.',
        'Endpoint advancement and previous buffers/STM/seed preservation, not whole original boot/first screen or full FPU.']},indent=2) + '\n')
print(f'PASS fresh FP32 continuation/sites{sites}/rebuild{rebuilt}/retain{125 - rebuilt}/previous buffers-STM-seed unchanged; {boundary}')

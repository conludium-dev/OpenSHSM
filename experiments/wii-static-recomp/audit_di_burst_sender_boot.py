"""Audit native inquiry ACK and retained requests, not completed DI replies."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'mass-di-burst-sender-boot'
base = root / 'mass-di86-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
for name in ('verify_di_burst_events_dolphin.py', 'verify_di_burst_sender_guard.py'):
    subprocess.run(['python3', str(experiment / name)], check=True)
build = json.loads((output / 'build.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_di_burst_sender_boot.py')
assert sha(output / 'openshsm-mass-boot') == build['executableSha256']
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
assert (output / 'di_burst_sender.h').read_bytes() == (experiment / 'di_burst_sender.h').read_bytes()
previous = json.loads((base / 'build.json').read_text())
assert len(build['records']) == len(previous['records']) == 125
for row, old in zip(build['records'], previous['records']):
    assert row['file'] == old['file'] and row['sourceSha256'] == old['sourceSha256']
    assert sha(Path(row['source'])) == row['sourceSha256']
    assert sha(Path(row['object'])) == row['objectSha256']
    if row['file'] not in ('output_62.cpp', 'output_65.cpp', 'output_67.cpp'):
        assert row['object'] == old['object']
for name in ('di_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'stm_device.cpp'):
    assert (output / name).read_bytes() == (base / name).read_bytes()
wrapper = (output / 'boot-wrapper.cpp').read_text()
first = wrapper[wrapper.index('    if (stmSubmitted == 31) {'):wrapper.index('    if (stmSubmitted == 25 ||')]
assert first == '    if (stmSubmitted == 31) {\n        experiment_di_burst_ack(context, request);\n        return;\n    }\n'
assert 'if (hw::ipc_ppc_msg != request || hw::ipc_ppc_ctrl != 0x31)' in wrapper
logs = {}
for mode in ('live', 'disabled'):
    env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
    env.update(SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin',
        SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF',
        SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')
    if mode == 'disabled':
        env['SHSM_DI86_DISABLED'] = '1'
    result = subprocess.run([str(output / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol',
        str(output / 'boot-quarantine.tsv'), str(root / 'sram-native/settings.bin')],
        env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 7 and not result.stderr, result.stdout + result.stderr
    logs[mode] = result.stdout + result.stderr
    (output / (mode + '-audit.log')).write_text(logs[mode])
live, disabled = logs['live'], logs['disabled']
assert [line for line in live.splitlines() if line.startswith('DI_BURST_PENDING_ACK ')] == [
    'DI_BURST_PENDING_ACK 135e0080', 'DI_BURST_PENDING_ACK 135e00e0']
assert 'BOOT_STM submitted=34 produced=14' in live
assert 'BOOT_BOUNDARY pc=80241c30 lr=8024204c msr=30' in live
assert 'reason=IPC reply write caller/value unverified' in live
assert 'BOOT_SI_DELIVERY entries=35 callbacks=4' in live
assert 'DI86_SOURCE 2' not in live and 'DI86_SOURCE 3' not in live
assert 'BOOT_STM submitted=30 produced=14' in disabled
assert 'BOOT_BOUNDARY pc=80241c30 lr=80242384 msr=2032' in disabled
assert 'DI_BURST_PENDING_ACK' not in disabled
(output / 'sender-audit.json').write_text(json.dumps({
    'result': 'NATIVE_INQUIRY_IRQ_SEND_ACK_TWO_PENDING_NEXT_ES_SENDER_PASS',
    'auditSha256': sha(Path(__file__)), 'buildSha256': sha(output / 'build.json'),
    'liveLogSha256': sha(output / 'live-audit.log'), 'disabledLogSha256': sha(output / 'disabled-audit.log'),
    'limits': ['Two request owners retained, source advances FIFO and sends second request underMSR30.',
        'Existing scheduler ACK64 is PC timing adaptation, not original hardware cycles.',
        'Third ES request BEFORE MMIO is next refusal; no DI replies/callbacks/inquiry output yet.',
        '79 component mutation tests use stub mapping/ACK; live logs separately prove real runtime progress.',
        'Full SI regression against same125 objects and completion/lifetime audit remain pending.']}, indent=2) + '\n')
print('PASS fresh native enabled34/14-35IRQ-two pending/disabled30/14;125sources122retained;79componentmutants; NEXT ES sender, no DI replies')

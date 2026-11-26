"""Check actual native path flush and compare prepared packet with original events."""
from pathlib import Path
import base64
import hashlib
import json
import os
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'mass-sysconf-path-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
base_path = root / 'mass-es-close-boot/build.json'
base = json.loads(base_path.read_text())
assert build['builderSha256'] == sha(experiment / 'build_sysconf_path_boot.py')
assert build['baseBuildSha256'] == sha(base_path)
assert build['parentBuilderSha256'] == sha(experiment / 'build_fs_open_boot.py')
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
assert len(build['records']) == 125
assert [row['file'] for row, old in zip(build['records'], base['records']) if row != old] == [
    'output_62.cpp', 'output_63.cpp', 'output_67.cpp']
for row, old in zip(build['records'], base['records']):
    assert row['sourceSha256'] == old['sourceSha256']
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for name in ('fs_device.cpp', 'es_device.cpp', 'stm_device.cpp', 'ipc_ack_frontend.h'):
    assert sha(output / name) == sha(base_path.parent / name)
for name, digest in base['headerHashes'].items():
    if Path(name).name != 'flush_syscall.h':
        assert sha(output / Path(name).name) == digest
capture_path = root / 'dolphin-sysconf-events-fixed-disc/fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
events = base64.b64decode(capture['events'])
send = events[64 + 47 * 1280:64 + 48 * 1280]
physical = bytearray(send[128:192])
cached = bytearray(send[64:128])
for packet in (physical, cached):
    struct.pack_into('>I', packet, 24, 0x80540010)


def check(lines, enabled):
    def values(prefix):
        matches = [line for line in lines if line.startswith(prefix + ' ')]
        assert len(matches) == 1, prefix
        return matches[0].split()[1:]

    assert 'BOOT_STM submitted=16 produced=7' in lines
    assert 'BOOT_STM_ASYNC dispatched=1 pending=1 6 1 324927520 4096 4796512 32 4796544 32' in lines
    assert 'BOOT_NAND_INIT_STATE 2' in lines
    assert 'BOOT_ES_CLOSE_STATE ffffffff 935e0060 50' in lines
    boundary = ' '.join(values('BOOT_BOUNDARY'))
    if enabled:
        assert boundary.startswith('pc=80241c30 lr=80242384 msr=2032')
        assert 'STM sender caller/value unverified' in boundary
        assert bytes(map(int, values('SC_PATH_PACKET_PHYSICAL'))) == physical
        assert bytes(map(int, values('SC_PATH_PACKET_CACHED'))) == cached
        assert bytes(map(int, values('SC_PATH_BYTES_PHYSICAL'))) == b'/shared2/sys/SYSCONF'.ljust(32, b'\0')
        assert values('BOOT_FLUSH') == ['entries=24', 'phase=0', 'barriers=18']
        assert values('SC_PATH_GATE') == ['1', '1'] + ['0'] * 11
    else:
        assert boundary.startswith('pc=80212ff4 lr=8024250c msr=a032')
        assert 'EE flush caller/pending-state unverified' in boundary
        assert values('BOOT_FLUSH') == ['entries=22', 'phase=0', 'barriers=16']
        assert values('SC_PATH_GATE') == ['0', '1'] + ['0'] * 11


exe = output / 'openshsm-mass-boot'
assert sha(exe) == build['executableSha256']
observations = {}
for mode in ('live', 'disabled'):
    env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
    env['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'
    if mode == 'disabled':
        env['SHSM_SYSCONF_PATH_DISABLED'] = '1'
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol',
        str(output / 'boot-quarantine.tsv'), str(root / 'sram-native/settings.bin')],
        env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 7 and not result.stderr
    (output / (mode + '-audit.log')).write_text(result.stdout)
    lines = result.stdout.splitlines()
    check(lines, mode == 'live')
    observations[mode] = lines
mutants = 0
for prefix in ('SC_PATH_PACKET_PHYSICAL', 'SC_PATH_PACKET_CACHED', 'SC_PATH_BYTES_PHYSICAL',
    'BOOT_FLUSH', 'SC_PATH_GATE', 'BOOT_STM submitted=', 'BOOT_STM_ASYNC dispatched='):
    changed = [line for line in observations['live'] if not line.startswith(prefix)]
    try:
        check(changed, True)
    except AssertionError:
        mutants += 1
    else:
        raise AssertionError('Corrupted observation accepted: ' + prefix)
(output / 'audit.json').write_text(json.dumps({'verifierSha256': sha(Path(__file__)),
    'buildSha256': sha(output / 'build.json'), 'oracleSha256': sha(capture_path),
    'result': 'NATIVE_PREPARED_ASYNC_OPEN_ORIGINAL_PACKET_MATCH_NO_SUBMISSION',
    'mutants': mutants, 'ignoredVirtualPointerRelocation': '8053ff90 -> 80540010',
    'limits': ['Path/packet cache maintenance only; no native OPEN response, file data or callback execution.']}, indent=2) + '\n')
print('PASS native path+packet flush/original64-byte views/explicit relocation/pending STM/disabled;7mutants; OPEN still guarded')

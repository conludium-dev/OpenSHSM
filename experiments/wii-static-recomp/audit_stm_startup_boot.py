"""Fresh guarded whole-DOL startup, with disabled STM admission control."""
from pathlib import Path
import hashlib
import json
import os
import struct
import subprocess

root = Path('work/private-game/static-recomp')
output = root / 'mass-stm-startup-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert build['builderSha256'] == sha(Path('experiments/wii-static-recomp/build_stm_startup_boot.py'))
assert build['baseBuildSha256'] == sha(root / 'mass-flush-packet-boot/build.json')
assert build['profileAttemptSha256'] == sha(root / 'stm-send-cycle/attempt.json')
assert build['profileComparisonSha256'] == sha(root / 'stm-send-cycle/comparison.json')
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
assert build['executableSha256'] == sha(output / 'openshsm-mass-boot')
assert build['quarantineSha256'] == sha(output / 'boot-quarantine.tsv')
oracle_path = root / 'dolphin-stm-send/comparison.json'
oracle = json.loads(oracle_path.read_text())['observations'][0]
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(original_path) == json.loads((root / 'dolphin-stm-send/generation.json').read_text())['originalSha256']
dol = original_path.read_bytes()
layout = struct.unpack('>64I', dol[:256])
for address, opcode in ((0x8021c8f8, 0x48025c59), (0x8021c900, 0x906dc400), (0x8021c920, 0x48025c31)):
    section = next(i for i in range(7) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
    assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == opcode
fresh = {}
for mode in ('live', 'disabled'):
    environment = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
    if mode == 'disabled':
        environment['SHSM_STM_STARTUP_DISABLED'] = '1'
    result = subprocess.run([str(output / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol',
        str(output / 'boot-quarantine.tsv'), str(root / 'sram-native/settings.bin')], env=environment,
        capture_output=True, text=True, timeout=30)
    (output / (mode + '-boot.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 7 and not result.stderr
    boundary = next(line for line in result.stdout.splitlines() if line.startswith('BOOT_BOUNDARY '))
    state = [line for line in result.stdout.splitlines() if line.startswith(('BOOT_STM', 'BOOT_SI_DELIVERY', 'BOOT_FLUSH'))]
    if mode == 'disabled':
        assert 'pc=80241c30 lr=80242384 msr=2032' in boundary
        assert 'BOOT_STM submitted=0 produced=0' in state
        assert 'BOOT_SI_DELIVERY entries=4 callbacks=4' in state
    else:
        assert 'pc=80241c30 lr=80242384 msr=2032' in boundary
        assert 'STM sender write profile unverified' in boundary
        assert 'BOOT_STM submitted=2 produced=1' in state
        assert 'BOOT_SI_DELIVERY entries=6 callbacks=4' in state
        assert 'BOOT_FLUSH entries=7 phase=0 barriers=7' in state
        complete = next(line for line in state if line.startswith('BOOT_STM_FIRST_COMPLETE ')).split()[1:]
        observed = {int(complete[i], 16): int(complete[i + 1], 16) for i in range(0, len(complete), 2)}
        assert observed == {0x8052ab20: oracle['replyResult'], 0x80528b70: 1, 0x8052ab00: 0, 0x8052ab04: 0,
            0x8052ab08: 0, 0x800000c0: 0x492658, 0x800000d4: 0x80492658, 0x800000d8: 0x80492658,
            0x800000e4: 0x80492658, 0x80492920: 0x20001, 0x804b2a80: 1, 0x804b2a84: 1,
            0x804b2a88: 1, 0x804b2a8c: 1, 0x804b2b44: 0, 0x804b2b4c: 0x935e0000, 0x935e0004: 4080}
        for marker, key in (('BOOT_STM_FIRST_PHYSICAL ', 'physicalPacketHex'), ('BOOT_STM_FIRST_CACHED ', 'cachedPacketHex')):
            values = next(line for line in state if line.startswith(marker)).split()[1:]
            assert bytes(map(int, values)).hex() == oracle[key]
        packet = next(line for line in state if line.startswith('BOOT_STM_NEXT_PACKET ')).split()[1:]
        assert int(packet[0]) == 0x135e0020
        assert bytes(map(int, packet[1:])) == struct.pack('>5I', 1, 0, 0, 0x439904, 0) + bytes(44)
        assert 'BOOT_STM_NEXT_PATH /dev/stm/eventhook' in state
    fresh[mode] = {'boundary': boundary, 'state': state, 'logSha256': sha(output / (mode + '-boot.log'))}
    print(mode + ': ' + boundary + '\n' + '\n'.join(state))
(output / 'audit.json').write_text(json.dumps({'result': 'WHOLE_DOL_FIRST_STM_OPEN_RETURN_FREE_MATCH_NEXT_EVENTHOOK_RETAINED',
    'auditorSha256': sha(Path(__file__)), 'buildSha256': sha(output / 'build.json'), 'fresh': fresh,
    'oracleSha256': sha(oracle_path), 'limits': build['limits'] + [
        'Original STM caller return/store instructions checked in own DOL; first completion packet matches isolated original oracle, not a full original startup trace.',
        'Existing whole-boot PI reset projection clears non-IPC10000 cause; native cause0 is preserved, not forced to oracle10000.',
        'Second eventhook request prepared but not submitted/completed; consecutive requests/eventhook support remains pending.']}, indent=2) + '\n')

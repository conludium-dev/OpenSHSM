"""Record whole-boot two-OPEN completion and guarded next request."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

parent = Path('experiments/wii-static-recomp/audit_stm_startup_boot.py')
prefix = parent.read_text().split('fresh = {}', 1)[0].replace('mass-stm-startup-boot', 'mass-stm-eventhook-boot').replace('build_stm_startup_boot.py', 'build_stm_eventhook_boot.py')
exec(compile(prefix, str(parent), 'exec'), globals())
assert build['parentBuilderSha256'] == sha(Path('experiments/wii-static-recomp/build_stm_startup_boot.py'))
assert build['pairOracleSha256'] == sha(root / 'dolphin-stm-pair/comparison.json')
assert build['ackOracleSha256'] == sha(root / 'dolphin-stm-pair-ack/comparison.json')
pair = json.loads((root / 'dolphin-stm-pair/comparison.json').read_text())['observations']
for address, opcode in ((0x8021c928, 0x906dc404), (0x8021c970, 0x48026381), (0x8021c95c, 0x3929cc70)):
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
    state = [line for line in result.stdout.splitlines() if line.startswith(('BOOT_STM', 'BOOT_FLUSH', 'BOOT_SI_DELIVERY'))]
    assert 'pc=80241c30 lr=80242384 msr=2032' in boundary
    if mode == 'disabled':
        assert 'BAT MMIO/locked-cache/unmapped backing access unavailable' in boundary
        assert 'BOOT_STM submitted=0 produced=0' in state
        assert 'BOOT_SI_DELIVERY entries=4 callbacks=4' in state
        assert 'BOOT_FLUSH entries=5 phase=0 barriers=5' in state
    else:
        assert 'STM sender caller/value unverified' in boundary
        assert 'BOOT_STM submitted=4 produced=2' in state
        assert 'BOOT_SI_DELIVERY entries=8 callbacks=4' in state
        assert 'BOOT_FLUSH entries=10 phase=0 barriers=a' in state
        assert 'BOOT_STM_FDS 0 1' in state
        for label, index in (('FIRST', 0), ('SECOND', 1)):
            values = next(line for line in state if line.startswith('BOOT_STM_' + label + '_COMPLETE ')).split()[1:]
            observed = {int(values[i], 16): int(values[i + 1], 16) for i in range(0, len(values), 2)}
            expected = {0x8052ab20: 0, 0x80528b70: 1, 0x8052ab00: 0, 0x8052ab04: 0, 0x8052ab08: 0,
                0x800000c0: 0x492658, 0x800000d4: 0x80492658, 0x800000d8: 0x80492658,
                0x800000e4: 0x80492658, 0x80492920: 0x20001, 0x804b2a80: index + 1,
                0x804b2a84: index + 1, 0x804b2a88: index + 1, 0x804b2a8c: index + 1,
                0x804b2b44: 0, 0x804b2b4c: 0x935e0000, 0x935e0004: 4080}
            assert observed == expected
            for view in ('PHYSICAL', 'CACHED'):
                values = next(line for line in state if line.startswith('BOOT_STM_' + label + '_' + view + ' ')).split()[1:]
                assert bytes(map(int, values)).hex() == pair[index][view.lower() + 'PacketHex']
        packet = next(line for line in state if line.startswith('BOOT_STM_NEXT_PACKET ')).split()[1:]
        assert int(packet[0]) == 0x135e0020
        assert bytes(map(int, packet[1:])) == struct.pack('>8I', 6, 1, 1, 0x1000, 0x493060, 32, 0x493080, 32) + bytes(32)
    fresh[mode] = {'boundary': boundary, 'state': state, 'logSha256': sha(output / (mode + '-boot.log'))}
    print(mode + ': ' + boundary + '\n' + '\n'.join(state))
(output / 'audit.json').write_text(json.dumps({'result': 'WHOLE_BOOT_TWO_STM_OPEN_FD0_FD1_REUSE_ORIGINAL_MATCH_NEXT_ASYNC_IOCTL_RETAINED', 'buildSha256': sha(output / 'build.json'),
    'auditorSha256': sha(Path(__file__)), 'fresh': fresh, 'limits': build['limits']}, indent=2) + '\n')

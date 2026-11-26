"""Fresh whole-boot async admission and retained two-OPEN control."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

parent = Path('experiments/wii-static-recomp/audit_stm_eventhook_boot.py')
prefix = parent.read_text().split('\nfresh = {}', 1)[0].replace('mass-stm-eventhook-boot', 'mass-stm-async-boot').replace('build_stm_eventhook_boot.py', 'build_stm_async_boot.py')
exec(compile(prefix, str(parent), 'exec'), globals())
assert build['asyncParentSha256'] == sha(Path('experiments/wii-static-recomp/build_stm_eventhook_boot.py'))
assert build['asyncOracleSha256'] == sha(root / 'dolphin-stm-async/comparison.json')
oracle = json.loads((root / 'dolphin-stm-async/comparison.json').read_text())['observations'][0]
profile = json.loads((root / 'stm-send-cycle/attempt.json').read_text())
for row, old in zip(build['records'], profile['records']):
    if row['file'] == 'main_output.cpp':
        extra = '\n            case 0x8021753C: func_80217520(ctx); break;'
        assert Path(row['source']).read_text().replace(extra, '', 1) == Path(old['source']).read_text()
    elif row['file'] == 'output_67.cpp':
        assert Path(row['source']).read_bytes() == Path(old['source']).read_bytes()
    else:
        assert row == old
for address, opcode in ((0x8021753c, 0x54838ffe), (0x8021c980, 0x900dc408), (0x8021c998, 0x900dc3fc)):
    section = next(i for i in range(7) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
    assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == opcode
irq_proof = root / 'ios-thread-cycle-irqs/ghidra/verification.json'
for record in json.loads(irq_proof.read_text())['records']:
    assert sha(irq_proof.parent / (record['name'] + '.asm')) == record['assemblySha256']
    assert sha(irq_proof.parent / (record['name'] + '.c')) == record['decompiledSha256']
fresh = {}
for mode in ('live', 'async-disabled'):
    environment = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
    if mode == 'async-disabled':
        environment['SHSM_STM_ASYNC_DISABLED'] = '1'
    result = subprocess.run([str(output / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol',
        str(output / 'boot-quarantine.tsv'), str(root / 'sram-native/settings.bin')], env=environment,
        capture_output=True, text=True, timeout=30)
    (output / (mode + '-boot.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 7 and not result.stderr
    boundary = next(line for line in result.stdout.splitlines() if line.startswith('BOOT_BOUNDARY '))
    state = [line for line in result.stdout.splitlines() if line.startswith(('BOOT_STM', 'BOOT_FLUSH', 'BOOT_SI_DELIVERY'))]
    assert 'BOOT_FLUSH entries=10 phase=0 barriers=a' in state
    if mode == 'async-disabled':
        assert 'pc=80241c30 lr=80242384 msr=2032' in boundary
        assert 'BOOT_STM submitted=4 produced=2' in state
        assert 'BOOT_SI_DELIVERY entries=8 callbacks=4' in state
        assert 'BOOT_STM_ASYNC dispatched=0 pending=0' in state
    else:
        assert 'pc=8020def4 lr=80240444 msr=a032' in boundary
        assert 'GetID MMIO profile mapping unverified' in boundary
        assert 'BOOT_STM submitted=6 produced=2' in state
        assert 'BOOT_SI_DELIVERY entries=9 callbacks=4' in state
        pending = next(line for line in state if line.startswith('BOOT_STM_ASYNC dispatched=')).split()
        assert pending[1:3] == ['dispatched=1', 'pending=1']
        assert list(map(int, pending[3:])) == [6, 1, 0x135e0020, 0x1000, 0x493060, 32, 0x493080, 32]
    values = next(line for line in state if line.startswith('BOOT_STM_ASYNC_MEMORY ')).split()[1:]
    memory = {int(values[i], 16): int(values[i + 1], 16) for i in range(0, len(values), 2)}
    assert memory[0x8052ab1c] == memory[0x8052ab28] == (1 if mode == 'live' else 0)
    assert memory[0x804b2b4c] == 0x935e0060 and memory[0x935e0004] == 0x50
    assert [memory[address] for address in (0x80528b70, 0x8052ab00, 0x8052ab04, 0x8052ab08)] == [1, 0, 0, 0]
    for view in ('PHYSICAL', 'CACHED'):
        values = next(line for line in state if line.startswith('BOOT_STM_ASYNC_' + view + ' ')).split()[1:]
        assert bytes(map(int, values)).hex() == oracle[view.lower() + 'PacketHex']
    fresh[mode] = {'boundary': boundary, 'state': state, 'logSha256': sha(output / (mode + '-boot.log'))}
    print(mode + ': ' + boundary + '\n' + '\n'.join(state))
(output / 'audit.json').write_text(json.dumps({'result': 'NATIVE_ASYNC_ACK_NO_REPLY_DEVICE_PENDING_SDK_REGISTRATION_ORIGINAL_MATCH', 'buildSha256': sha(output / 'build.json'),
    'auditorSha256': sha(Path(__file__)), 'fresh': fresh, 'limits': build['limits']}, indent=2) + '\n')

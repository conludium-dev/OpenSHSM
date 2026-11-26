"""Run the whole SC/NAND/FS chain with the measured native arena precondition."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_stm_async_dolphin.py')
native_arena = Path('work/private-game/static-recomp/mass-sysconf-arena-native/observation.json')
arena_report = json.loads(native_arena.read_text())
arena_lines = arena_report['observations']
assert 'SC_NATIVE_ARENA 935e2540 93600000 935e1000 93600000 935e1000 1 1' in arena_lines
body = parent.read_text().replace('dolphin-stm-async', 'dolphin-sysconf-chain').replace(
    'run_stm_async_dolphin.ps1', 'run_sysconf_chain_disc_dolphin.ps1')
marker = '        pointer(code, 9, 100000)'
assert body.count(marker) == 1
calls = '''        if index == 3:
            for address, value in [(0x8052afc4, 0x935e1000), (0x8052afc8, 0x93600000)]:
                pointer(code, 11, address)
                pointer(code, 0, value)
                code.append(dform(36, 0, 11, 0))
            callsite = base + len(code) * 4
            code.append(branch(callsite, 0x80247450, True))
        elif index >= 4:
            callsite = base + len(code) * 4
            code.append(branch(callsite, 0x802474f0, True))
        if index >= 3:
            code.extend([dform(36, 3, 30, 400), 0x7c0000a6, dform(36, 0, 30, 404)])
'''
body = body.replace(marker, calls + marker)
snapshot = '''        if index >= 3:
            for slot, address, size in [(448, 0x804b31a0, 32), (480, 0xc04b31a0, 32)]:
                pointer(code, 11, address)
                for offset in range(0, size, 4):
                    code.extend([dform(32, 0, 11, offset), dform(36, 0, 30, slot + offset)])
            for slot, displacement in [(608, -0x3718), (612, -0x3704), (616, -0x3702),
                (620, -0x374c), (624, -0x3748), (628, -0x3758), (632, -0x3744),
                (656, -0x373c), (660, -0x3738)]:
                code.extend([dform(34 if slot < 620 else 32, 0, 13, displacement), dform(36, 0, 30, slot)])
            code.append(dform(36, 13, 30, 644))
            for slot, address in [(648, 0x8052aa70), (708, 0x804b31a0), (712, 0x804b31a4),
                (716, 0x804b719c), (720, 0x804b3160), (724, 0x804b317c), (728, 0x804b3180),
                (732, 0x804b3158)]:
                pointer(code, 11, address)
                code.extend([dform(32, 0, 11, 0), dform(36, 0, 30, slot)])
'''
marker = '        pointer(code, 11, 0xc0493080)'
assert body.count(marker) == 1
body = body.replace(marker, snapshot + marker)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-sysconf-chain/generation.json')
report = json.loads(path.read_text())
report['sysconfChainParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['arenaPrecondition'] = {'low': '935e1000', 'high': '93600000',
    'nativeObservationSha256': hashlib.sha256(native_arena.read_bytes()).hexdigest(),
    'provenance': 'Read-only native __devfs/lo/hi bounds before the same original ISFS allocation, laboratory loader profile, not physical Wii bootstrap.'}
for case in report['records']:
    if case['index'] >= 3:
        case['kind'] = 'SCInit' if case['index'] == 3 else 'SCCheckStatus'
report['limits'] = ['Original whole SCInit owns NAND/FS/ES/title/CLOSE/file async lifecycle after live pending STM; no preparatory raw FS OPEN.',
    'Only measured available arena precondition supplied; no forced initialization/FD/SC status/callback result/file data.',
    'Boot/thread/arena laboratory fixture and emulator-generated system settings, not original disc assets/physical Wii NAND/full retail proof.']
path.write_text(json.dumps(report, indent=2) + '\n')

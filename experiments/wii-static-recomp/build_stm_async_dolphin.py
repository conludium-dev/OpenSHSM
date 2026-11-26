"""Original two OPENs followed by one IOS_IoctlAsync and bounded pending observations."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_stm_pair_dolphin.py')
body = parent.read_text().replace('dolphin-stm-pair', 'dolphin-stm-async').replace('run_stm_pair_dolphin.ps1', 'run_stm_async_dolphin.ps1')
pending = '''    else:
        data[index * stride:index * stride + 16] = b'OSHSM_PPC_DLP001'
        struct.pack_into('>I', data, index * stride + 20, index)
        pointer(code, 30, 0xc0680000 + index * stride)
        pointer(code, 24, 0xcd000000)
        pointer(code, 25, 0xcc003000)
        if index == 2:
            pointer(code, 1, 0x80540000)
            pointer(code, 2, 0x805335e0)
            pointer(code, 13, 0x8052e720)
            for register, value in [(3, 1), (4, 0x1000), (5, 0x80493060), (6, 32),
                (7, 0x80493080), (8, 32), (9, 0x8021cc70), (10, 0)]:
                pointer(code, register, value)
            async_call = base + len(code) * 4
            code.append(branch(async_call, 0x80242cf0, True))
            code.extend([dform(36, 3, 30, 400), 0x7c0000a6, dform(36, 0, 30, 404)])
            pointer(code, 0, 0xa032)
            code.append((31 << 26) | (146 << 1))
        pointer(code, 9, 100000)
        code.append(spr(9, 9, True))
        spin = base + len(code) * 4
        code.append(0x60000000)
        code.append(bc(base + len(code) * 4, spin, 16))
        for register, displacement, slot in [(24, 4, 24), (24, 8, 28), (25, 0, 32)]:
            code.extend([dform(32, 0, register, displacement), dform(36, 0, 30, slot)])
        for slot, address in enumerate([0x80528b70, 0x8052ab00, 0x8052ab04, 0x8052ab08,
            0x800000e4, 0x800000d4, 0x800000c0, 0x800000d8, 0x80492920,
            0x804b2b44, 0x804b2b4c, 0x935e0004, 0x804b2a80, 0x804b2a84,
            0x804b2a88, 0x804b2a8c, 0x804927f0, 0x804927f4]):
            pointer(code, 11, address)
            code.extend([dform(32, 0, 11, 0), dform(36, 0, 30, 36 + slot * 4)])
        code.extend([0x7c0000a6, dform(36, 0, 30, 108)])
        for cached, slot in [(False, 192), (True, 256)]:
            pointer(code, 11, 0x135e0020 | (0x80000000 if cached else 0xc0000000))
            for offset in range(0, 64, 4):
                code.extend([dform(32, 0, 11, offset), dform(36, 0, 30, slot + offset)])
        pointer(code, 11, 0xc0493080)
        for offset in range(0, 32, 4):
            code.extend([dform(32, 0, 11, offset), dform(36, 0, 30, 416 + offset)])
        pointer(code, 0, 0xc001cafe)
        code.append(dform(36, 0, 30, 16))
        records.append({'index': index, 'physical': 0x135e0020, 'kind': 'async-pending',
            'asyncCall': async_call, 'spinInstructions': 200000})
'''
extension = "start = body.index('\\nfor index in range(16):') + 1\nend = body.index('halt = base + len(code) * 4', start)\nloop = body[start:end].split('\\n', 1)[1]\nbody = body[:start] + 'for index in range(16):\\n    if index < 2:\\n' + ''.join('    ' + line + '\\n' for line in loop.splitlines()) + " + repr(pending) + " + body[end:]\n"
marker = 'marker = \'marker = "exec(compile(body, str(parent), \\\'exec\\\'), namespace)"\''
assert body.count(marker) == 1
body = body.replace(marker, 'extra += ' + repr(extension) + '\n' + marker, 1)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-stm-async/generation.json')
report = json.loads(path.read_text())
report['asyncParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Original two consecutive OPENs then one original IOS_IoctlAsync with callback8021CC70/userdata0, CPU-delivered ACK and bounded pending snapshots.',
    'No fake IOS reply/event or host power/reset action; observations cover a finite laboratory interval, not infinite waiting or callback completion.',
    'Prepared populated thread/heap/vector/queue, isolated Dolphin own Wii US0; not whole retail startup.']
path.write_text(json.dumps(report, indent=2) + '\n')

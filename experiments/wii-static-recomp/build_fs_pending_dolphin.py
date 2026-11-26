"""Original synchronous FS OPENs while one original STM request remains pending."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_stm_async_dolphin.py')
body = parent.read_text().replace('dolphin-stm-async', 'dolphin-fs-pending')
body = body.replace('run_stm_async_dolphin.ps1', 'run_fs_pending_dolphin.ps1')
marker = '        pointer(code, 9, 100000)'
addition = r'''        fs_call = 0
        if index >= 3:
            fs_path = b'/dev/fs\\0' if index < 10 else b'/dev/openshsm_missing\\0'
            fs_path = fs_path.ljust(64, b'\\0')
            pointer(code, 29, 0x935e1000)
            for offset in range(0, 64, 4):
                pointer(code, 0, int.from_bytes(fs_path[offset:offset + 4], 'big'))
                code.append(dform(36, 0, 29, offset))
            pointer(code, 3, 0x935e1000)
            pointer(code, 4, 0)
            fs_call = base + len(code) * 4
            code.append(branch(fs_call, 0x80242550, True))
            code.extend([dform(36, 3, 30, 400), 0x7c0000a6, dform(36, 0, 30, 404)])
'''
assert body.count(marker) == 1
body = body.replace(marker, addition + marker)
marker = '        pointer(code, 11, 0xc0493080)'
addition = '''        if index >= 3:
            for cached, slot in [(False, 448), (True, 512)]:
                pointer(code, 11, 0x135e0080 | (0x80000000 if cached else 0xc0000000))
                for offset in range(0, 64, 4):
                    code.extend([dform(32, 0, 11, offset), dform(36, 0, 30, slot + offset)])
            pointer(code, 11, 0xd35e1000)
            for offset in range(0, 64, 4):
                code.extend([dform(32, 0, 11, offset), dform(36, 0, 30, 576 + offset)])
'''
assert body.count(marker) == 1
body = body.replace(marker, addition + marker)
body = body.replace("'asyncCall': async_call, 'spinInstructions': 200000", "'asyncCall': async_call, 'spinInstructions': 200000, 'fsCall': fs_call, 'fsPath': '/dev/fs' if index < 10 else '/dev/openshsm_missing'")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-fs-pending/generation.json')
report = json.loads(path.read_text())
report['fsParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Original two STM OPENs and IOS_IoctlAsync, then seven whole IOS_Open /dev/fs and six missing-device controls; CPU IRQ/sleep/wakeup and shared heap/queue preserved.',
    'Prepared MEM2 path/stack/thread/vector/heap fixture, no original code patches; not ISFS_OpenLib or whole retail startup.',
    'No FS IOCTL/file reads/writes, callback completion, host power action or physical Wii timing proof.']
path.write_text(json.dumps(report, indent=2) + '\n')

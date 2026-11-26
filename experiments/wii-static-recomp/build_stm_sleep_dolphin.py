"""Run actual original OSSleepThread, idle-context IRQ and synchronous resumption."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_stm_irq_dolphin.py')
source = parent.read_text().replace('dolphin-stm-irq', 'dolphin-stm-sleep')
source = source.replace('run_stm_irq_dolphin.ps1', 'run_stm_sleep_dolphin.ps1')
start = source.index("waiting = '''")
end = source.index('\nassert body.count(marker) == 1', start)
source = source[:start] + "waiting = ''" + source[end:]
start = source.index("replacement = '''") + len("replacement = '''")
end = source.index('    code.extend([0x7c0000a6, dform(36, 0, 30, 76)])', start)
entry = '''    pointer(code, 28, 0x80492658)
    pointer(code, 3, (physical | 0x80000000) + 44)
    sleep_call = base + len(code) * 4
    code.append(branch(sleep_call, 0x8021b4e0, True))
    enable = sleep_call
    wait = 0x8021a8d8
    finished = 0x8021a908
'''
source = source[:start] + entry + source[end:]
source = source.replace('(0x804929f8, 68), (0x804929fc, 72)', '(0x804929f0, 68), (0x804929f4, 72)')
marker = '    for byte_offset in range(0, 64, 4):\n        code.extend([dform(32, 0, 26, byte_offset), dform(36, 0, 30, 192 + byte_offset)])'
assert source.count(marker) == 1
extra = '''    pointer(code, 11, 0x80492a70)
    for byte_offset, slot in [(0x198, 148), (0x19c, 152)]:
        code.extend([dform(32, 0, 11, byte_offset), dform(36, 0, 30, slot)])
    for address, slot in [(0x800000d4, 156), (0x800000c0, 160), (0x800000d8, 164)]:
        pointer(code, 11, address)
        code.extend([dform(32, 0, 11, 0), dform(36, 0, 30, slot)])
    for register, slot in [(1, 168), (2, 172), (13, 176), (30, 180)]:
        code.append(dform(36, register, 30, slot))
'''
source = source.replace(marker, extra + marker + '''
    pointer(code, 11, physical | 0x80000000)
    for byte_offset in range(0, 64, 4):
        code.extend([dform(32, 0, 11, byte_offset), dform(36, 0, 30, 256 + byte_offset)])''')
exec(compile(source, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-stm-sleep/generation.json')
report = json.loads(path.read_text())
report['sleepParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Whole original OSSleepThread/SelectThread/OSSaveContext/idle IRQ27/reply/WakeupThread/OSLoadContext/rfi; no direct handler/Wakeup call or code patches.',
    'Prepared populated current thread from native evidence, real wait-list insertion by original sleep; no manually sleeping/ready node.',
    'Original register-helper X1 submission and isolated emulator IOS mode0 STM/missing OPEN; no IOCTL/files/network.',
    'Lab uncached packet, initialized masks/context/vector, callerMSR2032 and prepared queue; not retail full IOS_Open caller or physical timing.']
path.write_text(json.dumps(report, indent=2) + '\n')

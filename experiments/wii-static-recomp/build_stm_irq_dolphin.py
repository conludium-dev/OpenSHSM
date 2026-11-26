"""Original CPU external vector/IPC IRQ27/reply/WakeupThread/rfi, prepared waiting node."""
from pathlib import Path
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
evidence_path = root / 'mass-ipc-irq-context-observer/irq-context.json'
evidence = json.loads(evidence_path.read_text())
assert evidence['layout']['0x800030ac'] == '0x80241f00'
thread_words = evidence['threadWords']
parent = experiment / 'build_stm_open_dolphin.py'
body = parent.read_text().replace("startup = '--startup-control' in sys.argv", 'startup = True')
body = body.replace("output_name = 'dolphin-stm-open-startup' if startup else 'dolphin-stm-open'", "output_name = 'dolphin-stm-irq'")
body = body.replace("wrapper_name = 'run_stm_open_startup_dolphin.ps1' if startup else 'run_stm_open_dolphin.ps1'", "wrapper_name = 'run_stm_irq_dolphin.ps1'")
marker = 'for index in range(16):'
assert body.count('\n' + marker) == 1
setup = '''vector_address = 0x80211ba0
section = next(i for i in range(7) if header[18 + i] <= vector_address < header[18 + i] + header[36 + i])
offset = header[section] + vector_address - header[18 + section]
vector_words = list(struct.unpack_from('>38I', original, offset))
assert vector_words[26] == 0x38600000
vector_words[26] = 0x38600004
code.extend([dform(14, 0, 0, 0x2032), (31 << 26) | (146 << 1)])
pointer(code, 11, 0xc0000500)
for word_index, word in enumerate(vector_words):
    pointer(code, 0, word)
    code.append(dform(36, 0, 11, word_index * 4))
code.append(0x7c0004ac)
'''
body = body.replace('\n' + marker, '\n' + setup + marker, 1)
marker = '    physical = 0x135e0020 + index * 64'
seed = '''    for address, value in [(0x800000c0, 0x00492658), (0x800000c4, 0xf7fff7e0), (0x800000c8, 0),
        (0x800000d4, 0x80492658), (0x800000d8, 0x80492658), (0x800000e4, 0x80492658),
        (0x80003010, 0x80217c60), (0x8052aad8, 0x80003040), (0x800030ac, 0x80241f00),
        (0x8052ab00, 0), (0x8052ab04, 0), (0x8052ab08, 0), (0x80528b70, 0),
        (0x8052afd8, 0), (0x8052afdc, 0)]:
        pointer(code, 11, address)
        pointer(code, 0, value)
        code.append(dform(36, 0, 11, 0))
    for thread_address in (0x80492658, 0x80690000):
        pointer(code, 11, thread_address)
        for word_index, value in enumerate(thread_words):
            pointer(code, 0, value)
            code.append(dform(36, 0, 11, word_index * 4))
    pointer(code, 11, 0x80492970)
    pointer(code, 0, 0)
    for byte_offset in range(0, 256, 4):
        code.append(dform(36, 0, 11, byte_offset))
    pointer(code, 11, 0x804b2a80)
    for word_index, value in enumerate([1, 1, 1, 1] + [0] * 16):
        pointer(code, 0, value)
        code.append(dform(36, 0, 11, word_index * 4))
'''
assert body.count(marker) == 1
body = body.replace(marker, seed + marker)
marker = '    path_address = 0x4398f0 if index < 8 else 0x6a1000'
waiting = '''    pointer(code, 28, 0x80690000)
    for byte_offset, value in [(0x2c8, 0x00040001), (0x2cc, 0), (0x2d0, 17), (0x2d4, 17),
        (0x2dc, (physical | 0x80000000) + 44), (0x2e0, 0), (0x2e4, 0)]:
        pointer(code, 0, value)
        code.append(dform(36, 0, 28, byte_offset))
    pointer(code, 0, 0x80690000)
    code.extend([dform(36, 0, 26, 44), dform(36, 0, 26, 48)])
'''
assert body.count(marker) == 1
body = body.replace(marker, waiting + marker)
start = body.index('    code.extend([dform(32, 0, 24, 4), dform(36, 0, 30, 32)])')
end = body.index('    pointer(code, 0, physical)', start)
replacement = '''    pointer(code, 0, 0xa032)
    enable = base + len(code) * 4
    code.append((31 << 26) | (146 << 1))
    pointer(code, 9, 1000000)
    code.append(spr(9, 9, True))
    wait = base + len(code) * 4
    code.extend([dform(32, 0, 26, 0), 0x2c000008])
    retry_packet = len(code)
    code.append(0)
    code.extend([dform(40, 0, 28, 0x2c8), 0x2c000001])
    retry_thread = len(code)
    code.append(0)
    code.extend([dform(32, 0, 24, 4), dform(28, 0, 0, 6)])
    complete = len(code)
    code.append(0)
    retry = base + len(code) * 4
    code.append(bc(base + len(code) * 4, wait, 16))
    code.extend([dform(14, 0, 0, 1), dform(36, 0, 30, 64)])
    finished = base + len(code) * 4
    code[retry_packet] = bc(base + retry_packet * 4, retry, 4, 2)
    code[retry_thread] = bc(base + retry_thread * 4, retry, 4, 2)
    code[complete] = bc(base + complete * 4, finished, 12, 2)
    code.extend([0x7c0000a6, dform(36, 0, 30, 76)])
    pointer(code, 0, 0x2032)
    code.append((31 << 26) | (146 << 1))
    for register, displacement, slot in [(24, 4, 32), (24, 8, 36), (25, 0, 40)]:
        code.extend([dform(32, 0, register, displacement), dform(36, 0, 30, slot)])
    for address, slot in [(0x80528b70, 44), (0x8052ab00, 48), (0x8052ab04, 52), (0x8052ab08, 56),
        (0x800000e4, 60), (0x804929f8, 68), (0x804929fc, 72), (0x8052aac8, 96)]:
        pointer(code, 11, address)
        code.extend([dform(32, 0, 11, 0), dform(36, 0, 30, slot)])
    pointer(code, 11, 0x8052aacc)
    code.extend([dform(40, 0, 11, 0), dform(36, 0, 30, 100)])
    pointer(code, 11, 0x80492658)
    for displacement, slot in [(0x198, 104), (0x19c, 108), (4, 112), (8, 116), (52, 120), (120, 124)]:
        code.extend([dform(32, 0, 11, displacement), dform(36, 0, 30, slot)])
    for displacement, slot in [(0x2c8, 128), (0x2d0, 132), (0x2dc, 136), (0x2e0, 140), (0x2e4, 144)]:
        code.extend([dform(32, 0, 28, displacement), dform(36, 0, 30, slot)])
    for byte_offset in range(0, 64, 4):
        code.extend([dform(32, 0, 26, byte_offset), dform(36, 0, 30, 192 + byte_offset)])
'''
body = body[:start] + replacement + body[end:]
body = body.replace("'send': send}", "'send': send, 'enable': enable, 'wait': wait, 'waitEnd': finished}")
namespace = {'__file__': __file__, 'thread_words': thread_words}
exec(compile(body, str(parent), 'exec'), namespace)
output = root / 'dolphin-stm-irq'
path = output / 'generation.json'
report = json.loads(path.read_text())
report['contextEvidenceSha256'] = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
report['parentGeneratorSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['vectorWords'] = namespace['vector_words']
report['limits'] = ['Original CPU vector/dispatcher/IPC IRQ27/reply/WakeupThread/SelectThread/rfi; no direct handler calls or original patches.',
    'Current populated thread context copied from native startup; separate waiting node priority17/state4 prepared using source fields.',
    'Current priority16 remains selected; actual OSSleepThread entry, higher-priority context switching, arbitrary FP restore and retail/physical timing unverified.',
    'Lab uncached MEM2 packets/EEon wait; no IOCTL/filewrite/network.']
path.write_text(json.dumps(report, indent=2) + '\n')

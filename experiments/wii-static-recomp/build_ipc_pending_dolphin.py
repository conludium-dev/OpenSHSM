"""Measure original reset against an ACK or reply from a read-only nonexistent-device open."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_template_copy_dolphin.py'
body = builder.read_text()

def replace(old, new):
    global body
    assert old in body, old
    body = body.replace(old, new)

replace('dolphin-template-copy', 'dolphin-ipc-pending')
replace('run_template_copy_dolphin.ps1', 'run_ipc_pending_dolphin.ps1')
replace('16 * stride', '8 * stride')
replace('range(16)', 'range(8)')
replace('store, target, template, length, memcpy = 0x802119a8, 0x80211c08', 'store, target, template, length, memcpy = 0x802175d4, 0xcd000034')
replace('0x901c0000', '0x90030034')
replace('data, code, records, returns =', '''def bc(position, target, bo, bi=0):
    displacement = target - position
    assert displacement % 4 == 0 and -32768 <= displacement < 32768
    return (16 << 26) | (bo << 21) | (bi << 16) | (displacement & 65532)

def delay(code, count):
    pointer(code, 9, count)
    code.append(spr(9, 9, True))
    location = len(code)
    code.append(bc(base + location * 4, base + location * 4, 16))

def poll(code, mask, failure_offset):
    pointer(code, 9, 1000000)
    code.append(spr(9, 9, True))
    location = len(code)
    code.extend([dform(32, 8, 3, 4), dform(28, 8, 8, mask)])
    success = len(code)
    code.append(0)
    code.append(bc(base + len(code) * 4, base + location * 4, 16))
    code.extend([dform(14, 0, 0, 1), dform(36, 0, 30, failure_offset)])
    code[success] = bc(base + success * 4, base + len(code) * 4, 4, 2)

data, code, records, returns =''')
replace('    pointer(code, 30, 0xc0000000 + result_base + index * stride)', '''    pointer(code, 30, 0xc0000000 + result_base + index * stride)
    code.extend([dform(50, 31, 30, 48), (63 << 26) | (255 << 17) | (31 << 11) | (711 << 1)])
    if index >= 4:
        code.append(branch(base + len(code) * 4, 0x80210830, True))
    pointer(code, 3, 0xcd000000)
    pointer(code, 4, 0xcc000000)
    pointer(code, 0, 0x40000000)
    code.append(dform(36, 0, 3, 0x34))
    pointer(code, 0, 6)
    code.append(dform(36, 0, 3, 4))
    pointer(code, 0, 0x40000000)
    code.append(dform(36, 0, 3, 0x30))
    pointer(code, 26, 0xc06a0000 + index * 64)
    pointer(code, 29, 0xc06a1000)
    path = b'/dev/openshsm_missing\\0'
    path += bytes((-len(path)) & 3)
    for offset in range(0, len(path), 4):
        pointer(code, 0, int.from_bytes(path[offset:offset + 4], 'big'))
        code.append(dform(36, 0, 29, offset))
    pointer(code, 0, 0)
    for offset in range(0, 64, 4):
        code.append(dform(36, 0, 26, offset))
    pointer(code, 0, 1)
    code.extend([dform(36, 0, 26, 0), dform(36, 0, 26, 0x10)])
    pointer(code, 0, 0x6a1000)
    code.append(dform(36, 0, 26, 0xc))
    pointer(code, 0, 0x6a0000 + index * 64)
    code.append(dform(36, 0, 3, 0))
    pointer(code, 0, 0x31)
    code.append(dform(36, 0, 3, 4))
    poll(code, 2, 64)
    if index & 2:
        pointer(code, 0, 0x32)
        code.append(dform(36, 0, 3, 4))
        pointer(code, 0, 0x40000000)
        code.append(dform(36, 0, 3, 0x30))
        poll(code, 4, 68)
    code.extend([dform(32, 0, 3, 4), dform(36, 0, 30, 32),
                 dform(32, 0, 3, 8), dform(36, 0, 30, 36),
                 dform(32, 0, 4, 0x3000), dform(36, 0, 30, 56),
                 dform(32, 0, 26, 0), dform(36, 0, 30, 92)])''')
replace('    pointer(code, 28, target)\n    pointer(code, 0, 0x38600000 | index)', '    pointer(code, 0, 0x40000000 if index & 1 else 0)')
replace("records.append({'index': index, 'value': 0x38600000 | index, 'destination': 0x80500000 + index * 256})",
        "records.append({'index': index, 'ni': index // 4, 'stage': 'reply' if index & 2 else 'ack', 'value': 0x40000000 if index & 1 else 0, 'request': 0x6a0000 + index * 64})")
start = body.index('observer = base + len(code) * 4')
end = body.index('while len(code) % 8:', start)
body = body[:start] + '''observer = base + len(code) * 4
code.append(dform(36, 0, 30, 24))
code.extend([dform(32, 0, 3, 4), dform(36, 0, 30, 28),
             dform(32, 0, 3, 8), dform(36, 0, 30, 40),
             dform(32, 0, 4, 0x3000), dform(36, 0, 30, 60)])
delay(code, 50000)
code.extend([dform(32, 0, 3, 4), dform(36, 0, 30, 72),
             dform(32, 0, 3, 8), dform(36, 0, 30, 76),
             dform(32, 0, 26, 0), dform(36, 0, 30, 80),
             dform(32, 0, 26, 4), dform(36, 0, 30, 84),
             dform(32, 0, 26, 8), dform(36, 0, 30, 88),
             (31 << 26) | (83 << 1), dform(36, 0, 30, 44),
             (63 << 26) | (583 << 1), dform(54, 0, 30, 704)])
for sweep in range(3):
    pointer(code, 0, 6)
    code.append(dform(36, 0, 3, 4))
    pointer(code, 0, 0x40000000)
    code.append(dform(36, 0, 3, 0x30))
    delay(code, 50000)
pointer(code, 0, 0xc001cafe)
code.append(dform(36, 0, 30, 16))
code.extend([spr(31, 9, True), 0x4e800420])
''' + body[end:]
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-ipc-pending/generation.json')
report = json.loads(path.read_text())
report['baseGeneratorSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['scope'] = 'Original802175D4 store/NI setter unchanged; adjacent exit802175D8; synthetic nonexistent-device OPEN/read-only request, ACK/reply polling and bounded later observation.'
report['requestPath'] = '/dev/openshsm_missing'
report['delayedLoopIterations'] = 50000
report['limits'] = ['No file creation/write/network request; isolated emulator IOS only, not original game I/O workflow.',
                    'Polling/delay counts are fixture bounds, not physical Wii timing or complete IOS/device semantics.']
for key in ('template', 'templateBytes', 'memcpy'):
    report.pop(key)
path.write_text(json.dumps(report, indent=2) + '\n')
print('Generated8originalIPC-store cases: ACK/reply×reset/noreset×NI0-NI1')

"""Measure original write-only IPC mask store through readable control/message state."""
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

replace('dolphin-template-copy', 'dolphin-ipc-reset')
replace('run_template_copy_dolphin.ps1', 'run_ipc_reset_dolphin.ps1')
replace('16 * stride', '32 * stride')
replace('range(16)', 'range(32)')
replace('store, target, template, length, memcpy = 0x802119a8, 0x80211c08', 'store, target, template, length, memcpy = 0x802175d4, 0xcd000034')
replace('0x901c0000', '0x90030034')
replace('    pointer(code, 30, 0xc0000000 + result_base + index * stride)', '''    pointer(code, 30, 0xc0000000 + result_base + index * stride)
    code.extend([dform(50, 31, 30, 48), (63 << 26) | (255 << 17) | (31 << 11) | (711 << 1)])
    if index >= 16:
        code.append(branch(base + len(code) * 4, 0x80210830, True))
    pointer(code, 3, 0xcd000000)
    pointer(code, 4, 0xcc000000)
    pointer(code, 0, 0)
    code.append(dform(36, 0, 3, 0x34))
    pointer(code, 0, ((index & 3) << 4) | 6)
    code.append(dform(36, 0, 3, 4))
    pointer(code, 0, 0x40000000)
    code.append(dform(36, 0, 3, 0x30))
    code.extend([dform(32, 0, 3, 4), dform(36, 0, 30, 32),
                 dform(32, 0, 3, 8), dform(36, 0, 30, 36),
                 dform(32, 0, 4, 0x3000), dform(36, 0, 30, 56)])''')
replace('    pointer(code, 28, target)\n    pointer(code, 0, 0x38600000 | index)', '''    values = [0, 0x40000000, 0x80000000, 0xffffffff]
    pointer(code, 0, values[(index & 15) // 4])''')
replace("records.append({'index': index, 'value': 0x38600000 | index, 'destination': 0x80500000 + index * 256})",
        "records.append({'index': index, 'ni': index // 16, 'value': values[(index & 15) // 4], 'priorControl': (index & 3) << 4})")
start = body.index('observer = base + len(code) * 4')
end = body.index('while len(code) % 8:', start)
body = body[:start] + '''observer = base + len(code) * 4
code.append(dform(36, 0, 30, 24))
code.extend([dform(32, 0, 3, 4), dform(36, 0, 30, 28),
             dform(32, 0, 3, 8), dform(36, 0, 30, 40),
             dform(32, 0, 4, 0x3000), dform(36, 0, 30, 60),
             (31 << 26) | (83 << 1), dform(36, 0, 30, 44),
             (63 << 26) | (583 << 1), dform(54, 0, 30, 704)])
pointer(code, 0, 0xc001cafe)
code.append(dform(36, 0, 30, 16))
code.extend([spr(31, 9, True), 0x4e800420])
''' + body[end:]
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-ipc-reset/generation.json')
report = json.loads(path.read_text())
report['baseGeneratorSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['scope'] = 'Original802175D4 IPC-mask store/NI setter unchanged; adjacent exit802175D8, synthetic IRQmask0/control-IY1-IY2/ACK+IRQflagclear/register/cache fixtures, EE0.'
report['limits'] = ['No read from write-only PPC_IRQMASK/PPCMSG; observations cover control and zero ARM message only.',
                    'Nonzero/in-flight messages, IOS services, queued events/external delivery and full OS init unverified.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('Generated32originalIPC-mask cases:4values×4controlseeds×NI0-NI1, EE0')

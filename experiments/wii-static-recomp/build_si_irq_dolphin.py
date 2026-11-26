"""Measure callback-present SI packets through the original interrupt handler."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_si_query_dolphin.py'
body = builder.read_text().replace('dolphin-si-query', 'dolphin-si-irq').replace('run_si_query_dolphin.ps1', 'run_si_irq_dolphin.ps1')
assert body.count('    pointer(code, 8, 0)') == 1
body = body.replace('    pointer(code, 8, 0)', '    pointer(code, 8, 0x80210110)')
marker = '    pointer(code, 11, 0x8042b708 + channel * 4)'
seed = '''    pointer(code, 11, 0x80492010)
    pointer(code, 0, 0xffffffff)
    for offset in (0, 32, 64, 96):
        code.append(dform(36, 0, 11, offset))
'''
body = body.replace(marker, seed + marker, 1)
marker = "    code.append(branch(base + len(code) * 4, 0x8020f550, True))"
assert body.count(marker) == 1
body = body.replace(marker, '''    pointer(code, 3, 20)
    pointer(code, 4, 0x80501000)
    code.append(branch(base + len(code) * 4, 0x8020f850, True))
    code.append(dform(32, 3, 30, 108))''')
marker = '    pointer(code, 0, 0xc001cafe)'
assert body.count(marker) == 1
body = body.replace(marker, '''    pointer(code, 11, 0x8042b708 + channel * 4)
    code.extend([dform(32, 0, 11, 0), dform(36, 0, 30, 92)])
    pointer(code, 11, 0xcc000000)
    code.extend([dform(32, 0, 11, 0x3000), dform(36, 0, 30, 96)])
    pointer(code, 11, 0x8042b700)
    code.extend([dform(32, 0, 11, 0), dform(36, 0, 30, 100)])
''' + marker)
marker = 'while len(code) % 8:'
assert body.count(marker) == 1
body = body.replace(marker, '''address, opcode = 0x80210110, 0x9421ffe0
section = next(i for i in range(7) if header[18 + i] <= address < header[18 + i] + header[36 + i])
offset = header[section] + address - header[18 + section]
assert struct.unpack_from('>I', original, offset)[0] == opcode
trampoline = base + len(code) * 4
code.extend([opcode, dform(36, 11, 1, -8), dform(36, 12, 1, -4)])
pointer(code, 11, 0xc06e0000)
code.extend([dform(32, 11, 11, 0), dform(36, 3, 11, 104), dform(36, 4, 11, 108),
             dform(32, 11, 1, -8), dform(32, 12, 1, -4)])
code.append(branch(base + len(code) * 4, address + 4))
patches.append({'address': address, 'offset': offset, 'opcode': opcode, 'trampoline': trampoline, 'kind': 'callback'})
''' + marker)
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-si-irq/generation.json')
report = json.loads(path.read_text())
report['baseGeneratorSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
for record in report['records']:
    record['callback'] = 0x80210110
report['scope'] = 'Whole original setupFD00/hardware START wait/SIInterruptHandlerF850/original completionF550/bctrl GetTypeCallback10110; handler called explicitly by fixture, not CPU exception-vector delivery.'
report['limits'] = ['Prepared idle Si owner/types/empty Packet queue/r2-r13/MSR/HID and context argument; automatic CPU external IRQ/alarm/retail startup not proven.',
    'Four None SI ports, no attached controller/Wiimote/physical Wii/game image. Three observers replay displaced instructions and preserve r11/r12/CR/LR.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('Generated16 callback-present original SI handler calls; completion and callback run inside original handler')

"""Use the existing SI fixture with real CPU external-exception delivery."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_si_irq_dolphin.py'
source = parent.read_text()
marker = "exec(compile(body, str(builder), 'exec'), {'__file__': __file__})"
assert source.count(marker) == 1
namespace = {'__file__': __file__}
exec(compile(source.split(marker)[0], str(parent), 'exec'), namespace)
body = namespace['body'].replace('dolphin-si-irq', 'dolphin-si-vector').replace('run_si_irq_dolphin.ps1', 'run_si_vector_dolphin.ps1')
marker = 'for index in range(16):'
assert body.count(marker) == 1
body = body.replace(marker, '''vector_address = 0x80211ba0
section = next(i for i in range(7) if header[18 + i] <= vector_address < header[18 + i] + header[36 + i])
vector_offset = header[section] + vector_address - header[18 + section]
vector_words = list(struct.unpack_from('>38I', original, vector_offset))
assert vector_words[26] == 0x38600000
vector_words[26] = 0x38600004
code.extend([dform(14, 0, 0, 0x2030), (31 << 26) | (146 << 1)])
pointer(code, 11, 0xc0000500)
for index, word in enumerate(vector_words):
    pointer(code, 0, word)
    code.append(dform(36, 0, 11, index * 4))
code.append(0x7c0004ac)
for address, value in [(0x800000c0, 0x00501000), (0x800000d4, 0x80501000),
        (0x800000c4, 0xfffff7ff), (0x800000c8, 0), (0x80003010, 0x80217c60),
        (0x8052aad8, 0x80003040), (0x80003090, 0x8020f850),
        (0x8052ab00, 0), (0x8052ab04, 0), (0xcc003004, 8)]:
    pointer(code, 11, address)
    pointer(code, 0, value)
    code.append(dform(36, 0, 11, 0))
vector_records = []
''' + marker)
marker = '''    pointer(code, 3, 20)
    pointer(code, 4, 0x80501000)
    code.append(branch(base + len(code) * 4, 0x8020f850, True))
    code.append(dform(32, 3, 30, 108))'''
assert body.count(marker) == 1
body = body.replace(marker, '''    pointer(code, 11, 0x80501000)
    pointer(code, 0, 0)
    for offset in range(0, 0x1c8, 4):
        code.append(dform(36, 0, 11, offset))
    pointer(code, 0, 0xa032)
    enable = base + len(code) * 4
    code.append((31 << 26) | (146 << 1))
    wait_callback = base + len(code) * 4
    code.extend([dform(32, 0, 30, 108), 0x2c000000])
    code.append(0x41820000 | ((wait_callback - (base + len(code) * 4)) & 0xfffc))
    code.append(0x7c0000a6)
    code.append(dform(36, 0, 30, 112))
    pointer(code, 0, 0x2030)
    code.append((31 << 26) | (146 << 1))
    pointer(code, 11, 0x80501000)
    for offset, slot in [(0x198, 116), (0x19c, 120), (4, 124), (8, 128), (52, 132), (120, 136)]:
        code.extend([dform(32, 0, 11, offset), dform(36, 0, 30, slot)])
    code.extend([dform(40, 0, 11, 0x1a2), dform(36, 0, 30, 140)])
    for address, slot in [(0x8052ab00, 144), (0x8052ab04, 148), (0x8052aac8, 152)]:
        pointer(code, 11, address)
        code.extend([dform(32, 0, 11, 0), dform(36, 0, 30, slot)])
    pointer(code, 11, 0x8052aacc)
    code.extend([dform(40, 0, 11, 0), dform(36, 0, 30, 156)])
    vector_records.append({'enable': enable, 'wait': wait_callback, 'waitEnd': wait_callback + 12})
    code.append(dform(32, 3, 30, 108))''')
namespace = {'__file__': __file__}
exec(compile(body, str(namespace.get('builder', parent)), 'exec'), namespace)
output = Path('work/private-game/static-recomp/dolphin-si-vector')
path = output / 'generation.json'
report = json.loads(path.read_text())
report['baseGeneratorSha256'] = hashlib.sha256((experiment / 'build_si_query_dolphin.py').read_bytes()).hexdigest()
report['irqGeneratorSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['vectorWords'] = namespace['vector_words']
report['vectorRecords'] = namespace['vector_records']
for record in report['records']:
    record['callback'] = 0x80210110
report['scope'] = 'Original SI packet with PI mask8/MSR EE+RI; CPU enters copied original external vector500, original dispatcher selects SI IRQ20, OSLoadContext/rfi returns to interrupted fixture.'
report['limits'] = ['Prepared vector copy/exception ID4/OSContext/tables/software masks/scheduler hint0; not retail startup or physical Wii.',
    'Four None ports and existing three replaying observers; no attached-controller/Wiimote/timing/full-register/first-frame acceptance.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('Generated16 CPU-delivered SI packets; no direct handler call')

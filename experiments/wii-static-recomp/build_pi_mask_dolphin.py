"""Measure original PI mask store with EE disabled and explicit NI fixtures."""
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

replace('dolphin-template-copy', 'dolphin-pi-mask')
replace('run_template_copy_dolphin.ps1', 'run_pi_mask_dolphin.ps1')
replace('16 * stride', '32 * stride')
replace('range(16)', 'range(32)')
replace('store, target, template, length, memcpy = 0x802119a8, 0x80211c08', 'store, target, template, length, memcpy = 0x802175d0, 0xcc003004')
replace('0x901c0000', '0x90a43004')
replace('    pointer(code, 30, 0xc0000000 + result_base + index * stride)', '''    pointer(code, 30, 0xc0000000 + result_base + index * stride)
    code.extend([dform(50, 31, 30, 48), (63 << 26) | (255 << 17) | (31 << 11) | (711 << 1)])
    if index >= 16:
        code.append(branch(base + len(code) * 4, 0x80210830, True))
    pointer(code, 4, 0xcc000000)
    pointer(code, 0, 0x10203040 if index & 1 else 0)
    code.append(dform(36, 0, 4, 0x3004))
    code.extend([dform(32, 0, 4, 0x3004), dform(36, 0, 30, 32),
                 dform(32, 0, 4, 0x3000), dform(36, 0, 30, 36)])''')
replace('    pointer(code, 28, target)\n    pointer(code, 0, 0x38600000 | index)', '''    values = [0, 0xf0, 0xffffffff, 0x100, 0x10000, 0x10100, 0x80000000, 0x12345678,
              1, 2, 4, 8, 0x10, 0x20, 0x40, 0x4000]
    pointer(code, 5, values[index & 15])''')
replace("records.append({'index': index, 'value': 0x38600000 | index, 'destination': 0x80500000 + index * 256})",
        "records.append({'index': index, 'ni': index // 16, 'value': values[index & 15], 'priorMask': 0x10203040 if index & 1 else 0})")
start = body.index('observer = base + len(code) * 4')
end = body.index('while len(code) % 8:', start)
body = body[:start] + '''observer = base + len(code) * 4
code.append(dform(36, 5, 30, 24))
code.extend([dform(32, 0, 4, 0x3004), dform(36, 0, 30, 28),
             dform(32, 0, 4, 0x3000), dform(36, 0, 30, 40),
             (31 << 26) | (83 << 1), dform(36, 0, 30, 44),
             (63 << 26) | (583 << 1), dform(54, 0, 30, 704)])
pointer(code, 0, 0xc001cafe)
code.append(dform(36, 0, 30, 16))
code.extend([spr(31, 9, True), 0x4e800420])
''' + body[end:]
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-pi-mask/generation.json')
report = json.loads(path.read_text())
report['baseGeneratorSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['scope'] = 'Original802175D0 PI mask store and NI setter unchanged; observer exit802175D4, synthetic masks/register/cache fixture, EE disabled.'
report['limits'] = ['Mask readback only; asynchronous producers/cause timing, external exception delivery and full OS loop unverified.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('Generated32originalPI-mask store cases,16values atNI0/NI1 withEE0')

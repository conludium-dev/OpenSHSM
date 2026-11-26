"""Measure the unchanged original MI mask store with disclosed register fixtures."""
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


replace('dolphin-template-copy', 'dolphin-mi-mask')
replace('run_template_copy_dolphin.ps1', 'run_mi_mask_dolphin.ps1')
replace('16 * stride', '32 * stride')
replace('range(16)', 'range(32)')
replace('store, target, template, length, memcpy = 0x802119a8, 0x80211c08', 'store, target, template, length, memcpy = 0x802176e4, 0xcc00401c')
replace('0x901c0000', '0xb0a4401c')
replace('    pointer(code, 30, 0xc0000000 + result_base + index * stride)', '''    pointer(code, 30, 0xc0000000 + result_base + index * stride)
    code.extend([dform(50, 31, 30, 48), (63 << 26) | (255 << 17) | (31 << 11) | (711 << 1)])
    if index >= 16:
        code.append(branch(base + len(code) * 4, 0x80210830, True))
    values = [0, 1, 31, 65535]
    pointer(code, 4, 0xcc000000)
    pointer(code, 5, values[index & 3])
    code.extend([dform(44, 5, 4, 0x401c), dform(40, 0, 4, 0x401c), dform(36, 0, 30, 32),
                 dform(32, 0, 4, 0x3000), dform(36, 0, 30, 56)])''')
replace('    pointer(code, 28, target)\n    pointer(code, 0, 0x38600000 | index)', '    pointer(code, 5, values[(index & 15) // 4])')
replace("records.append({'index': index, 'value': 0x38600000 | index, 'destination': 0x80500000 + index * 256})",
        "records.append({'index': index, 'ni': index // 16, 'value': values[(index & 15) // 4], 'priorMask': values[index & 3]})")
start = body.index('observer = base + len(code) * 4')
end = body.index('while len(code) % 8:', start)
body = body[:start] + '''observer = base + len(code) * 4
code.append(dform(36, 5, 30, 24))
code.extend([dform(40, 0, 4, 0x401c), dform(36, 0, 30, 28),
             dform(32, 0, 4, 0x3000), dform(36, 0, 30, 60),
             (31 << 26) | (83 << 1), dform(36, 0, 30, 44),
             (63 << 26) | (583 << 1), dform(54, 0, 30, 704)])
pointer(code, 0, 0xc001cafe)
code.append(dform(36, 0, 30, 16))
code.extend([spr(31, 9, True), 0x4e800420])
''' + body[end:]
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-mi-mask/generation.json')
report = json.loads(path.read_text())
report['baseGeneratorSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['scope'] = 'Original MI sth802176E4 unchanged; adjacent BLR802176E8 observer patch, synthetic mask seeds/registers/MSR/HID0/NI0-NI1; no full SetInterruptMask execution.'
report['limits'] = ['Readback of MI mask and PI cause only; no memory protection faults or interrupt delivery.', 'Owned private Dolphin measurement; no physical Wii or complete startup equivalence claim.']
path.write_text(json.dumps(report, indent=2) + '\n')

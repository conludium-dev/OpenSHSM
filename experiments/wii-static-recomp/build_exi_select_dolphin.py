"""Measure original channel0 select block from a disclosed post-init seed."""
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


replace('dolphin-template-copy', 'dolphin-exi-select')
replace('run_template_copy_dolphin.ps1', 'run_exi_select_dolphin.ps1')
replace('store, target, template, length, memcpy = 0x802119a8, 0x80211c08', 'store, target, template, length, memcpy = 0x8020e3c0, 0xcd006800')
replace('0x901c0000', '0x80646800')
replace('    pointer(code, 30, 0xc0000000 + result_base + index * stride)', '''    pointer(code, 30, 0xc0000000 + result_base + index * stride)
    code.extend([dform(50, 31, 30, 48), (63 << 26) | (255 << 17) | (31 << 11) | (711 << 1)])
    if index >= 8:
        code.append(branch(base + len(code) * 4, 0x80210830, True))
    pointer(code, 4, 0xcd000000)
    if index == 0:
        code.extend([dform(14, 0, 0, 0), dform(36, 0, 4, 0x6800), dform(14, 0, 0, 0x2000), dform(36, 0, 4, 0x6800)])
    code.extend([dform(32, 0, 4, 0x6800), dform(36, 0, 30, 32)])
    pointer(code, 6, 0xcc000000)
    code.extend([dform(32, 0, 6, 0x3000), dform(36, 0, 30, 56)])
    device, clock = [2, 0, 1, 2][index & 3], (index >> 2) & 1''')
replace('    pointer(code, 28, target)\n    pointer(code, 0, 0x38600000 | index)', '    pointer(code, 28, device)\n    pointer(code, 29, clock)')
replace("records.append({'index': index, 'value': 0x38600000 | index, 'destination': 0x80500000 + index * 256})", "records.append({'index': index, 'ni': index // 8, 'device': device, 'clock': clock})")
start = body.index('observer = base + len(code) * 4')
end = body.index('while len(code) % 8:', start)
body = body[:start] + '''observer = base + len(code) * 4
code.extend([dform(36, 3, 30, 24), dform(32, 0, 4, 0x6800), dform(36, 0, 30, 28)])
pointer(code, 6, 0xcc000000)
code.extend([dform(32, 0, 6, 0x3000), dform(36, 0, 30, 60),
             (31 << 26) | (83 << 1), dform(36, 0, 30, 44),
             (63 << 26) | (583 << 1), dform(54, 0, 30, 704)])
pointer(code, 0, 0xc001cafe)
code.append(dform(36, 0, 30, 16))
code.extend([spr(31, 9, True), 0x4e800420])
''' + body[end:]
replace('store_offset + 4', 'store_offset + 0x24')
replace('store + 4', 'store + 0x24')
replace('Generated16 original store/template-copy cases; one adjacent observer patch, no original store/memcpy edits', 'Generated16 original EXISelect CSR cases; post-init seed3800, boundary observer only')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-exi-select/generation.json')
report = json.loads(path.read_text())
report['baseGeneratorSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['scope'] = 'Original select8020E3C0..E3E0 unchanged; nextE3E4 observer. Prepared channel0 post-init3800 seed, devices0/1/2, clocks0/1, NI0/1.'
report['limits'] = ['CSR selection only; no full eligibility/lock/restore/device protocol or physical Wii behavior.']
path.write_text(json.dumps(report, indent=2) + '\n')

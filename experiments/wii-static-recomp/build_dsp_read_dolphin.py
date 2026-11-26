"""Observe the original boot DSP read without seeding the DSP register."""
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


replace('dolphin-template-copy', 'dolphin-dsp-read')
replace('run_template_copy_dolphin.ps1', 'run_dsp_read_dolphin.ps1')
replace('store, target, template, length, memcpy = 0x802119a8, 0x80211c08',
        'store, target, template, length, memcpy = 0x802176f4, 0xcc00500a')
replace('0x901c0000', '0xa0a5500a')
replace('    pointer(code, 30, 0xc0000000 + result_base + index * stride)', '''    pointer(code, 30, 0xc0000000 + result_base + index * stride)
    code.extend([dform(50, 31, 30, 48), (63 << 26) | (255 << 17) | (31 << 11) | (711 << 1)])
    if index >= 8:
        code.append(branch(base + len(code) * 4, 0x80210830, True))
    pointer(code, 4, 0xcc000000)
    code.extend([dform(32, 0, 4, 0x3000), dform(36, 0, 30, 56)])''')
replace('    pointer(code, 28, target)\n    pointer(code, 0, 0x38600000 | index)',
        '    pointer(code, 5, 0xcc000000)')
replace("records.append({'index': index, 'value': 0x38600000 | index, 'destination': 0x80500000 + index * 256})",
        "records.append({'index': index, 'ni': index // 8})")
start = body.index('observer = base + len(code) * 4')
end = body.index('while len(code) % 8:', start)
body = body[:start] + '''observer = base + len(code) * 4
code.append(dform(36, 5, 30, 24))
code.extend([dform(32, 0, 4, 0x3000), dform(36, 0, 30, 60),
             (31 << 26) | (83 << 1), dform(36, 0, 30, 44),
             (63 << 26) | (583 << 1), dform(54, 0, 30, 704)])
pointer(code, 0, 0xc001cafe)
code.append(dform(36, 0, 30, 16))
code.extend([spr(31, 9, True), 0x4e800420])
''' + body[end:]
replace('Generated16 original store/template-copy cases; one adjacent observer patch, no original store/memcpy edits',
        'Generated16 original DSP read cases; unseeded DSP, one adjacent observer patch')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-dsp-read/generation.json')
report = json.loads(path.read_text())
report['baseGeneratorSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['scope'] = 'Original lhz802176F4 unchanged; next instruction802176F8 redirects to observer. Unseeded Dolphin DSP, synthetic registers/MSR/HID0/NI.'
report['limits'] = ['Loader initial DSP read only; no prior original startup, DSP writes, audio, DMA or physical Wii evidence.']
path.write_text(json.dumps(report, indent=2) + '\n')

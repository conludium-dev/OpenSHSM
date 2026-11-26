"""Measure the original reset store after synthetic prior ID writes."""
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

replace('dolphin-template-copy', 'dolphin-reset-copy')
replace('run_template_copy_dolphin.ps1', 'run_reset_copy_dolphin.ps1')
replace('16 * stride', '32 * stride')
replace('range(16)', 'range(32)')
replace('store, target, template, length, memcpy = 0x802119a8', 'store, target, template, length, memcpy = 0x80211b0c')
replace('0x901c0000', '0x937c0000')
replace('    pointer(code, 30, 0xc0000000 + result_base + index * stride)', '''    pointer(code, 30, 0xc0000000 + result_base + index * stride)
    code.extend([dform(50, 31, 30, 40), (63 << 26) | (255 << 17) | (31 << 11) | (711 << 1)])
    if index >= 16:
        code.append(branch(base + len(code) * 4, 0x80210830, True))''')
replace('pointer(code, 27, 0x80500000 + index * 256)', 'pointer(code, 26, 0x80500000 + index * 256)')
replace('pointer(code, 0, 0x38600000 | index)', '''pointer(code, 0, 0x38600000 | (index & 15))
    code.append(dform(36, 0, 28, 0))
    code.extend([dform(32, 0, 28, 0), dform(36, 0, 30, 36)])
    pointer(code, 27, 0x38600000)''')
replace("'index': index, 'value': 0x38600000 | index", "'index': index, 'ni': index // 16, 'priorValue': 0x38600000 | (index & 15), 'value': 0x38600000")
replace('code.append(dform(36, 0, 30, 24))', '''code.append(dform(36, 27, 30, 24))
code.extend([(63 << 26) | (583 << 1), dform(54, 0, 30, 704)])''')
replace('dform(24, 27, 3, 0)', 'dform(24, 26, 3, 0)')
replace('dform(32, 0, 27, offset)', 'dform(32, 0, 26, offset)')
replace('pointer(code, 0, 0xc001cafe)', '''code.extend([(63 << 26) | (583 << 1), dform(54, 0, 30, 712)])
pointer(code, 0, 0xc001cafe)''')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-reset-copy/generation.json')
report = json.loads(path.read_text())
report['baseGeneratorSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['scope'] = 'Original reset store80211B0C/memcpy/NI setter unchanged; synthetic prior-ID write/readback, registers, cached ordinary-RAM destinations and adjacent exit80211B10 observer.'
report['limits'] = ['Synthetic32fixtures, not full exception initialization, real vectors, relocated dispatch or physical Wii timing.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('Generated32original reset-store cases: priorID0..15, NI0/NI1')

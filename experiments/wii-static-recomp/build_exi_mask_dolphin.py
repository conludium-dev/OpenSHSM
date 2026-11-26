"""Measure three unchanged original EXI mask blocks on loader channel state."""
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


replace('dolphin-template-copy', 'dolphin-exi-mask')
replace('run_template_copy_dolphin.ps1', 'run_exi_mask_dolphin.ps1')
replace('16 * stride', '48 * stride')
replace('range(16)', 'range(48)')
replace('store, target, template, length, memcpy = 0x802119a8, 0x80211c08', 'store, target, template, length, memcpy = 0x80217758, 0xcd006800')
replace('0x901c0000', '0x54800253')
replace('    pointer(code, 30, 0xc0000000 + result_base + index * stride)', '''    pointer(code, 30, 0xc0000000 + result_base + index * stride)
    code.extend([dform(50, 31, 30, 48), (63 << 26) | (255 << 17) | (31 << 11) | (711 << 1)])
    if index >= 24:
        code.append(branch(base + len(code) * 4, 0x80210830, True))
    channel = (index // 8) % 3
    entry = [0x80217758, 0x8021779c, 0x802177e0][channel]
    bits = index & (3 if channel == 2 else 7)
    mask = 0xffffffff ^ (bits << [20, 17, 15][channel])
    pointer(code, 4, 0xcc000000)
    code.extend([dform(32, 0, 4, 0x3000), dform(36, 0, 30, 56)])''')
replace('    pointer(code, 28, target)\n    pointer(code, 0, 0x38600000 | index)', '''    pointer(code, 28, target + channel * 20)
    code.extend([dform(32, 0, 28, 0), dform(36, 0, 30, 32)])
    pointer(code, 3, 1 << [22, 19, 16][channel])
    pointer(code, 4, mask)''')
replace('branch(base + len(code) * 4, store, True)', 'branch(base + len(code) * 4, entry, True)')
replace("records.append({'index': index, 'value': 0x38600000 | index, 'destination': 0x80500000 + index * 256})", "records.append({'index': index, 'ni': index // 24, 'channel': channel, 'softwareMask': mask})")
start = body.index('observer = base + len(code) * 4')
end = body.index('while len(code) % 8:', start)
body = body[:start] + '''observer = base + len(code) * 4
code.extend([dform(36, 5, 30, 24), dform(32, 0, 28, 0), dform(36, 0, 30, 28)])
pointer(code, 4, 0xcc000000)
code.extend([dform(32, 0, 4, 0x3000), dform(36, 0, 30, 60),
             (31 << 26) | (83 << 1), dform(36, 0, 30, 44),
             (63 << 26) | (583 << 1), dform(54, 0, 30, 704)])
pointer(code, 0, 0xc001cafe)
code.append(dform(36, 0, 30, 16))
code.extend([spr(31, 9, True), 0x4e800420])
''' + body[end:]
replace("struct.pack_into('>I', image, store_offset + 4, branch(store + 4, observer))", '''patches = []
for exit_address in (0x80217798, 0x802177dc, 0x80217810):
    offset = header[section] + exit_address - header[18 + section]
    assert struct.unpack_from('>I', original, offset)[0] == 0x4e800020
    struct.pack_into('>I', image, offset, branch(exit_address, observer))
    patches.append({'address': exit_address, 'offset': offset})''')
replace("'exitPatchOffset': store_offset + 4, 'exitPatchAddress': store + 4,", "'exitPatches': patches,")
replace('Generated16 original store/template-copy cases; one adjacent observer patch, no original store/memcpy edits', 'Generated48 original EXI mask cases; three return observers, original blocks unchanged')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-exi-mask/generation.json')
report = json.loads(path.read_text())
report['baseGeneratorSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['scope'] = 'Original EXI blocks unchanged; three BLR observers only; unseeded channels, synthetic software masks/MSR/HID0/NI.'
report['limits'] = ['Loader device/channel state only; no EXI transfers/active DMA/device protocol/physical Wii/full preceding startup.']
path.write_text(json.dumps(report, indent=2) + '\n')

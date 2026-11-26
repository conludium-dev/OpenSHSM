"""Measure original idle polling and four CSR initialization writes."""
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


replace('dolphin-template-copy', 'dolphin-exi-init')
replace('run_template_copy_dolphin.ps1', 'run_exi_init_dolphin.ps1')
replace('16 * stride', '32 * stride')
replace('range(16)', 'range(32)')
replace('store, target, template, length, memcpy = 0x802119a8, 0x80211c08', 'store, target, template, length, memcpy = 0x8020e910, 0xcd006800')
replace('0x901c0000', '0x8003680c')
replace('    pointer(code, 30, 0xc0000000 + result_base + index * stride)', '''    pointer(code, 30, 0xc0000000 + result_base + index * stride)
    code.extend([dform(50, 31, 30, 48), (63 << 26) | (255 << 17) | (31 << 11) | (711 << 1)])
    if index >= 16:
        code.append(branch(base + len(code) * 4, 0x80210830, True))
    pointer(code, 4, 0xcc000000)
    code.extend([dform(32, 0, 4, 0x3000), dform(36, 0, 30, 56)])
    pointer(code, 3, 0xcd000000)
    for channel in range(3):
        code.extend([dform(32, 0, 3, 0x6800 + channel * 20), dform(36, 0, 30, 192 + channel * 4),
                     dform(32, 0, 3, 0x680c + channel * 20), dform(36, 0, 30, 204 + channel * 4)])
    entry = 0x8020e94c if index & 1 else 0x8020e910''')
replace('    pointer(code, 28, target)\n    pointer(code, 0, 0x38600000 | index)', '    pointer(code, 28, 0)')
replace('branch(base + len(code) * 4, store, True)', 'branch(base + len(code) * 4, entry, True)')
replace("records.append({'index': index, 'value': 0x38600000 | index, 'destination': 0x80500000 + index * 256})", "records.append({'index': index, 'ni': index // 16, 'mode': index & 1})")
start = body.index('observer = base + len(code) * 4')
end = body.index('while len(code) % 8:', start)
body = body[:start] + '''observer = base + len(code) * 4
code.append(dform(36, 0, 30, 24))
for channel in range(3):
    code.extend([dform(32, 0, 3, 0x6800 + channel * 20), dform(36, 0, 30, 216 + channel * 4),
                 dform(32, 0, 3, 0x680c + channel * 20), dform(36, 0, 30, 228 + channel * 4)])
pointer(code, 4, 0xcc000000)
code.extend([dform(32, 0, 4, 0x3000), dform(36, 0, 30, 60),
             (31 << 26) | (83 << 1), dform(36, 0, 30, 44),
             (63 << 26) | (583 << 1), dform(54, 0, 30, 704)])
pointer(code, 0, 0xc001cafe)
code.append(dform(36, 0, 30, 16))
code.extend([spr(31, 9, True), 0x4e800420])
''' + body[end:]
replace("struct.pack_into('>I', image, store_offset + 4, branch(store + 4, observer))", '''patches = []
for exit_address, expected in ((0x8020e940, 0x3c600080), (0x8020e968, 0x38600009)):
    offset = header[section] + exit_address - header[18 + section]
    assert struct.unpack_from('>I', original, offset)[0] == expected
    struct.pack_into('>I', image, offset, branch(exit_address, observer))
    patches.append({'address': exit_address, 'offset': offset, 'opcode': expected})''')
replace("'exitPatchOffset': store_offset + 4, 'exitPatchAddress': store + 4,", "'exitPatches': patches,")
replace('Generated16 original store/template-copy cases; one adjacent observer patch, no original store/memcpy edits', 'Generated32 original EXI idle-poll/CSR-init cases; two boundary observers')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-exi-init/generation.json')
report = json.loads(path.read_text())
report['baseGeneratorSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['scope'] = 'Original poll8020E910..93C and CSR writes8020E94C..964 unchanged; two boundary observers. Synthetic registers/MSR/HID0/NI, unseeded EXI.'
report['limits'] = ['Idle polling and CSR initialization only; no full EXIInit/masking/handler/device-ID path or active transfer/physical Wii proof.']
path.write_text(json.dumps(report, indent=2) + '\n')

"""Add replaying DSP command/read observers to the whole original audio fixture."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/build_audio_init_dolphin.py')
body = parent.read_text().replace('dolphin-audio-init', 'dolphin-audio-trace').replace('run_audio_init_dolphin.ps1', 'run_audio_trace_dolphin.ps1')
marker = "exec(compile(prefix, str(parent), 'exec'), globals())"
assert body.count(marker) == 1
body = body.replace(marker, "prefix = prefix.replace('0x680000, 736', '0x680000, 1024')\n" + marker)
marker = '    pointer(code, 31, 0x55660000 + index)'
body = body.replace(marker, marker + '\n    pointer(code, 11, 0xc06e0000)\n    code.append(dform(36, 30, 11, 0))')
marker = 'patches = []'
assert body.count(marker) == 1
observers = '''patches = []
sites = [0x80212d40, 0x80212d48, 0x80212d4c, 0x80212d54, 0x80212d6c,
    0x80212d8c, 0x80212d98, 0x80212d9c, 0x80212db8, 0x80212ddc,
    0x80212de8, 0x80212dec, 0x80212e08, 0x80212e0c, 0x80212e14,
    0x80212e28, 0x80212e30, 0x80212e34, 0x80212e54, 0x80212e58, 0x80212e60,
    0x80212e64, 0x80212e68, 0x80212e70]
for address in sites:
    section = next(i for i in range(7) if header[18 + i] <= address < header[18 + i] + header[36 + i])
    offset = header[section] + address - header[18 + section]
    opcode = struct.unpack_from('>I', original, offset)[0]
    primary, register, ra = opcode >> 26, (opcode >> 21) & 31, (opcode >> 16) & 31
    assert primary in (36, 40, 44) and register not in (11, 12) and ra in (3, 4)
    displacement = opcode & 65535
    trampoline = base + len(code) * 4
    words = [opcode, dform(36, 11, 1, -8), dform(36, 12, 1, -4)]
    pointer(words, 11, 0xc06e0000)
    words.extend([dform(32, 11, 11, 0), dform(32, 12, 11, 100), dform(14, 12, 12, 1),
        dform(36, 12, 11, 100), dform(14, 12, 12, -1),
        (21 << 26) | (12 << 21) | (12 << 16) | (4 << 11) | (27 << 1),
        (31 << 26) | (11 << 21) | (11 << 16) | (12 << 11) | (266 << 1)])
    words.append(dform(36, register, 11, 548))
    pointer(words, 12, address)
    words.append(dform(36, 12, 11, 544))
    words.extend([dform(14, 12, ra, displacement), dform(36, 12, 11, 552), spr(12, 268, False),
        dform(36, 12, 11, 556), dform(32, 11, 1, -8), dform(32, 12, 1, -4)])
    words.append(branch(trampoline + len(words) * 4, address + 4))
    code.extend(words)
    patches.append({'address': address, 'offset': offset, 'opcode': opcode, 'trampoline': trampoline, 'words': words,
        'kind': 'read' if primary == 40 else 'write', 'width': 4 if primary == 36 else 2})
'''
body = body.replace(marker, observers)
body = body.replace("'No original instruction patch; final state/memory only, command chronology and intermediate DMA/mailbox state not observed.'",
    "'24replaying observers preserve r11/r12/CR/LR; observation overhead, no physical timing/full-register/interrupt claim.'")
body = body.replace('Generated16whole original audio startup calls, no executable patches', 'Generated16whole audio startup calls with24replaying DSP observers')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})

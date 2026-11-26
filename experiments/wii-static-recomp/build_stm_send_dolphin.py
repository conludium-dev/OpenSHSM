"""Execute original heap allocation and whole __IPCSend, not direct IRQ calls."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_stm_sleep_dolphin.py')
body = parent.read_text().replace('dolphin-stm-sleep', 'dolphin-stm-send').replace('run_stm_sleep_dolphin.ps1', 'run_stm_send_dolphin.ps1')
transform = '''body = body.replace('(0x80528b70, 0)', '(0x80528b70, 1)')
body = body.replace('    write_register(1, 0x38)', '    write_register(1, 0x30)')
marker = '    pointer(code, 26, physical | 0xc0000000)'
heap = ''' + repr('''    pointer(code, 11, 0x804b2b40)
    pointer(code, 0, 0)
    for byte_offset in range(0, 128, 4):
        code.append(dform(36, 0, 11, byte_offset))
    pointer(code, 3, (physical | 0x80000000) - 32)
    pointer(code, 4, 4096)
    code.append(branch(base + len(code) * 4, 0x80243570, True))
    code.append(dform(36, 3, 30, 328))
    pointer(code, 11, 0x80528b74)
    code.append(dform(36, 3, 11, 0))
    pointer(code, 3, 0)
    pointer(code, 4, 64)
    pointer(code, 5, 32)
    code.append(branch(base + len(code) * 4, 0x802438a0, True))
    code.append(dform(36, 3, 30, 324))
    pointer(code, 11, 0xc0000c00)
    flush_section = next(i for i in range(7) if header[18 + i] <= 0x8021a120 < header[18 + i] + header[36 + i])
    flush_offset = header[flush_section] + 0x8021a120 - header[18 + flush_section]
    for word_index, word in enumerate(struct.unpack_from('>7I', original, flush_offset)):
        pointer(code, 0, word)
        code.append(dform(36, 0, 11, word_index * 4))
    code.append(0x7c0004ac)
''') + '''
assert body.count(marker) == 1
body = body.replace(marker, heap + '    pointer(code, 26, physical | 0x80000000)')
start = body.index('    call = write_register(0, physical)')
end = body.index('    code.extend([0x7c0000a6, dform(36, 0, 30, 76)])', start)
entry = ''' + repr('''    pointer(code, 28, 0x80492658)
    pointer(code, 26, physical | 0xc0000000)
    pointer(code, 3, physical | 0x80000000)
    pointer(code, 4, 0)
    call = base + len(code) * 4
    code.append(branch(call, 0x802421f0, True))
    code.append(dform(36, 3, 30, 320))
    enable = call
    wait = 0x8021a8d8
    finished = 0x8021a908
''') + '''
body = body[:start] + entry + body[end:]
marker = '    pointer(code, 0, physical)'
extra = ''' + repr('''    for word_index, address in enumerate([0x804b2b40, 0x804b2b44, 0x804b2b48, 0x804b2b4c,
        (physical | 0x80000000) - 32, (physical | 0x80000000) - 28,
        0x804b2a80, 0x804b2a84, 0x804b2a88, 0x804b2a8c]):
        pointer(code, 11, address)
        code.extend([dform(32, 0, 11, 0), dform(36, 0, 30, 332 + word_index * 4)])
''') + '''
assert body.count(marker) == 1
body = body.replace(marker, extra + marker)
'''
marker = "exec(compile(body, str(parent), 'exec'), namespace)"
injection = "source = source.replace(" + repr(marker) + ", " + repr(transform + marker) + ", 1)\n"
marker = "exec(compile(source, str(parent), 'exec'), {'__file__': __file__})"
assert body.count(marker) == 1
body = body.replace(marker, injection + marker, 1)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-stm-send/generation.json')
report = json.loads(path.read_text())
report['sendParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Original heap create/allocate and whole __IPCSend including flush/queue/register submission/sleep/reply/free; no direct handler/Wakeup calls.',
    'Prepared thread/context/queue/heap arena and mode0 STM/missing requests on own Wii US0; not whole IOS_Open caller or retail boot.',
    'Private isolated Dolphin interpreter/cache profile, not physical Wii timing; no IOCTL/files/network.']
path.write_text(json.dumps(report, indent=2) + '\n')

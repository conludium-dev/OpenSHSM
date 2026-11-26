"""Observe original ACK prior-ARM retention across a pending STM and changed FS packets."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_stm_pair_ack_dolphin.py')
body = parent.read_text().replace('dolphin-stm-pair-ack', 'dolphin-fs-ack').replace('run_stm_pair_ack_dolphin.ps1', 'run_fs_ack_dolphin.ps1')
marker = "exec(compile(body, str(parent), 'exec'), {'__file__': __file__})"
extra = '''body = body.replace('physical = 0x135e0020', 'physical = 0x135e0020 if index < 3 else 0x135e0080 + (index - 3) * 64')
body = body.replace('path_address = 0x4398f0 if not index % 2 else 0x439904', 'path_address = (0x4398f0 if index == 0 else 0x439904) if index < 3 else 0x135e1000')
needle = '    pointer(code, 0, path_address)'
path_setup = "    if index >= 3:\\n        pointer(code, 29, 0xd35e1000)\\n        for offset, value in [(0, 0x2f646576), (4, 0x2f667300)]:\\n            pointer(code, 0, value)\\n            code.append(dform(36, 0, 29, offset))\\n"
assert body.count(needle) == 1
body = body.replace(needle, path_setup + needle)
needle = '    code.extend([dform(32, 0, 24, 4), dform(36, 0, 30, 24)])'
ioctl = "    if index == 2:\\n        for offset, value in enumerate([6, 0, 1, 0x1000, 0x493060, 32, 0x493080, 32]):\\n            pointer(code, 0, value)\\n            code.append(dform(36, 0, 26, offset * 4))\\n"
assert body.count(needle) == 1
body = body.replace(needle, ioctl + needle)
start = body.index('    poll(4, 68)')
end = body.index('    code.extend([dform(32, 0, 24, 4), dform(36, 0, 30, 60)', start)
block = body[start:end]
body = body[:start] + '    if index != 2:\\n' + ''.join('    ' + line + '\\n' for line in block.splitlines()) + body[end:]
needle = '    pointer(code, 0, physical)'
capture = "    for cached, slot in [(False, 256), (True, 320)]:\\n        pointer(code, 11, 0x135e0020 | (0x80000000 if cached else 0xc0000000))\\n        for offset in range(0, 64, 4):\\n            code.extend([dform(32, 0, 11, offset), dform(36, 0, 30, slot + offset)])\\n"
assert body.count(needle) == 1
body = body.replace(needle, capture + needle)
'''
assert body.count(marker) == 1
body = body.replace(marker, extra + marker)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-fs-ack/generation.json')
report = json.loads(path.read_text())
for case in report['records']:
    index = case['index']
    case['kind'] = 'prepared-stm-ioctl-pending' if index == 2 else 'open'
    case['path'] = '/dev/stm/immediate' if index == 0 else '/dev/stm/eventhook' if index < 3 else '/dev/fs'
report['fsAckParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Original register-helper EE-off poll: two STM OPENs, prepared command6/FD1/ioctl1000 with no reply, thirteen FS OPENs with changing packet pointers.',
    'Prepared uncached requests, not SDK allocation/heap/cache-metadata ownership or CPU handler chronology; complements separate whole IOS_Open pending oracle.',
    'No original instruction patches, file writes/reads, FS IOCTL, host power/network or physical Wii timing proof.']
path.write_text(json.dumps(report, indent=2) + '\n')

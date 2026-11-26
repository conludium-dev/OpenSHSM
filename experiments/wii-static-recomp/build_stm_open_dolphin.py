"""Original register-helper submission, ACK/reply and64-byte MEM2 OPEN payload capture."""
from pathlib import Path
import hashlib
import json
import struct
import sys

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_si_query_dolphin.py'
source = parent.read_text()
startup = '--startup-control' in sys.argv
output_name = 'dolphin-stm-open-startup' if startup else 'dolphin-stm-open'
wrapper_name = 'run_stm_open_startup_dolphin.ps1' if startup else 'run_stm_open_dolphin.ps1'
send = 0x31 if startup else 0x39
prefix = source[:source.index('for index in range(16):')].replace('dolphin-si-query', output_name)
exec(compile(prefix, str(parent), 'exec'), globals())
def bc(position, target, bo, bi=0):
    displacement = target - position
    assert displacement % 4 == 0 and -32768 <= displacement < 32768
    return (16 << 26) | (bo << 21) | (bi << 16) | (displacement & 65532)
def write_register(index, value):
    pointer(code, 3, index)
    pointer(code, 4, value)
    call = base + len(code) * 4
    code.append(branch(call, 0x80241c30, True))
    return call
def poll(mask, failure):
    pointer(code, 9, 1000000)
    code.append(spr(9, 9, True))
    location = len(code)
    code.extend([dform(32, 8, 24, 4), dform(28, 8, 8, mask)])
    success = len(code)
    code.append(0)
    code.append(bc(base + len(code) * 4, base + location * 4, 16))
    code.extend([dform(14, 0, 0, 1), dform(36, 0, 30, failure)])
    code[success] = bc(base + success * 4, base + len(code) * 4, 4, 2)
for index in range(16):
    data[index * stride:index * stride + 16] = b'OSHSM_PPC_DLP001'
    struct.pack_into('>I', data, index * stride + 20, index)
    code.extend([dform(14, 0, 0, 0x2032), (31 << 26) | (146 << 1)])
    pointer(code, 1, 0x80540000)
    pointer(code, 2, 0x805335e0)
    pointer(code, 13, 0x8052e720)
    pointer(code, 30, 0xc0680000 + index * stride)
    pointer(code, 24, 0xcd000000)
    pointer(code, 25, 0xcc003000)
    pointer(code, 0, 0x40f8)
    code.append(dform(36, 0, 25, 4))
    pointer(code, 0, 0x40000000)
    code.extend([dform(36, 0, 24, 0x34), dform(36, 0, 24, 0x30)])
    write_register(1, 6)
    write_register(1, 0x38)
    physical = 0x135e0020 + index * 64
    pointer(code, 26, physical | 0xc0000000)
    pointer(code, 0, 0)
    for offset in range(0, 64, 4):
        code.append(dform(36, 0, 26, offset))
    pointer(code, 0, 1)
    code.append(dform(36, 0, 26, 0))
    path_address = 0x4398f0 if index < 8 else 0x6a1000
    if index >= 8:
        pointer(code, 29, 0xc06a1000)
        path = b'/dev/openshsm_missing\0'
        path += bytes((-len(path)) & 3)
        for offset in range(0, len(path), 4):
            pointer(code, 0, int.from_bytes(path[offset:offset + 4], 'big'))
            code.append(dform(36, 0, 29, offset))
    pointer(code, 0, path_address)
    code.append(dform(36, 0, 26, 12))
    code.extend([dform(32, 0, 24, 4), dform(36, 0, 30, 24)])
    call = write_register(0, physical)
    code.extend([dform(36, 0, 30, 84), dform(36, 4, 30, 88), spr(0, 8, False), dform(36, 0, 30, 92),
        dform(32, 0, 24, 0), dform(36, 0, 30, 28)])
    write_register(1, send)
    code.extend([dform(32, 0, 24, 4), dform(36, 0, 30, 32)])
    poll(2, 64)
    for register, displacement, slot in [(24, 4, 36), (24, 8, 40), (25, 0, 44)]:
        code.extend([dform(32, 0, register, displacement), dform(36, 0, 30, slot)])
    write_register(1, (send & 0x38) | 2)
    pointer(code, 0, 0x40000000)
    code.append(dform(36, 0, 24, 0x30))
    poll(4, 68)
    for register, displacement, slot in [(24, 4, 48), (24, 8, 52), (25, 0, 56)]:
        code.extend([dform(32, 0, register, displacement), dform(36, 0, 30, slot)])
    for offset in range(0, 64, 4):
        code.extend([dform(32, 0, 26, offset), dform(36, 0, 30, 192 + offset)])
    write_register(1, (send & 0x38) | 4)
    pointer(code, 0, 0x40000000)
    code.append(dform(36, 0, 24, 0x30))
    code.extend([dform(32, 0, 24, 4), dform(36, 0, 30, 60), dform(32, 0, 25, 0), dform(36, 0, 30, 72),
        0x7c0000a6, dform(36, 0, 30, 76)])
    pointer(code, 0, physical)
    code.append(dform(36, 0, 30, 80))
    pointer(code, 0, 0xc001cafe)
    code.append(dform(36, 0, 30, 16))
    records.append({'index': index, 'physical': physical, 'pathAddress': path_address, 'mode': 0,
        'path': '/dev/stm/immediate' if index < 8 else '/dev/openshsm_missing', 'messageCall': call, 'messageReturn': call + 4, 'send': send})
halt = base + len(code) * 4
code.append(branch(halt, halt))
patches = []
exec(compile(source[source.index('while len(code) % 8:'):source.index('sha = lambda path:')], str(parent), 'exec'), globals())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'generation.json').write_text(json.dumps({'originalSha256': sha(original_path),
    'harnessSha256': sha(output / 'fpr-init.dol'), 'generatorSha256': sha(Path(__file__)),
    'parentSha256': sha(parent), 'helperSha256': sha(helpers), 'wrapperSha256': sha(experiment / wrapper_name),
    'baseRunnerSha256': sha(experiment / 'run_dolphin_probe.ps1'), 'records': records, 'patches': [],
    'limits': ['Whole original register helper; laboratory MEM2 uncached packet and polling with EEoff, not whole IOS_Open caller/IRQ chain.',
        'Eight STM opens/eight nonexistent-device controls; no file writes, IOCTLs or network. Handles remain in isolated emulator until exit.',
        'Zero64-byte request preparation/mode0; startup packet tail beyond32bytes not yet measured. Poll counts not physical timing.']}, indent=2) + '\n')
print('Generated16MEM2 mode0 OPEN exchanges; original helper/unpatched DOL, ACK/reply/full64-byte capture')

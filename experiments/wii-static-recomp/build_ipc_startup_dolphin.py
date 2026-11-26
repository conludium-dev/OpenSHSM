"""Measure whole original IPCWriteReg cold X2 write with observed enabled-interrupt mask."""
from pathlib import Path
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_si_query_dolphin.py'
source = parent.read_text()
exec(compile(source[:source.index('for index in range(16):')].replace('dolphin-si-query', 'dolphin-ipc-startup'), str(parent), 'exec'), globals())
for index in range(16):
    data[index * stride:index * stride + 16] = b'OSHSM_PPC_DLP001'
    struct.pack_into('>I', data, index * stride + 20, index)
    code.extend([dform(14, 0, 0, 0x2032), (31 << 26) | (146 << 1)])
    pointer(code, 1, 0x80540000)
    pointer(code, 2, 0x805335e0)
    pointer(code, 13, 0x8052e720)
    pointer(code, 30, 0xc0680000 + index * stride)
    pointer(code, 11, 0xcc003004)
    pointer(code, 0, 0x40f8)
    code.append(dform(36, 0, 11, 0))
    pointer(code, 3, 1)
    pointer(code, 4, 6)
    code.append(branch(base + len(code) * 4, 0x80241c30, True))
    pointer(code, 11, 0xcd000004)
    code.extend([dform(32, 0, 11, 0), dform(36, 0, 30, 24)])
    pointer(code, 11, 0xcc003000)
    code.extend([dform(32, 0, 11, 0), dform(36, 0, 30, 28)])
    pointer(code, 0, 0xa032)
    code.append((31 << 26) | (146 << 1))
    pointer(code, 3, 1)
    pointer(code, 4, 0x38)
    call = base + len(code) * 4
    code.append(branch(call, 0x80241c30, True))
    for register, slot in [(0, 32), (3, 36), (4, 40), (1, 44), (2, 48), (13, 52)]:
        code.append(dform(36, register, 30, slot))
    code.extend([spr(0, 8, False), dform(36, 0, 30, 56), 0x7c0000a6, dform(36, 0, 30, 60)])
    for address, slot in [(0xcd000004, 64), (0xcc003000, 68), (0xcc003004, 72)]:
        pointer(code, 11, address)
        code.extend([dform(32, 0, 11, 0), dform(36, 0, 30, slot)])
    pointer(code, 0, 0xc001cafe)
    code.append(dform(36, 0, 30, 16))
    records.append({'index': index, 'call': call, 'return': call + 4})
halt = base + len(code) * 4
code.append(branch(halt, halt))
patches = []
exec(compile(source[source.index('while len(code) % 8:'):source.index('sha = lambda path:')], str(parent), 'exec'), globals())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'generation.json').write_text(json.dumps({'originalSha256': sha(original_path),
    'harnessSha256': sha(output / 'fpr-init.dol'), 'generatorSha256': sha(Path(__file__)), 'parentSha256': sha(parent),
    'helperSha256': sha(helpers), 'wrapperSha256': sha(experiment / 'run_ipc_startup_dolphin.ps1'),
    'baseRunnerSha256': sha(experiment / 'run_dolphin_probe.ps1'), 'records': records, 'patches': [],
    'limits': ['Original register helper unpatched; original clear6prepares control0, labmask40F8/ABI/MSRA032.',
        'No IOS requests/retail loader/physical Wii or full client-init execution.']}, indent=2) + '\n')
print('Generated16whole unpatched original cold IPC control38 writes withEE/RI and mask40F8')

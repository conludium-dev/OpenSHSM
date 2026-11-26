"""Run both original OSGetResetCode branches without changing the function."""
from pathlib import Path
import hashlib
import json
import struct
experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_si_query_dolphin.py'
source = parent.read_text()
exec(compile(source[:source.index('for index in range(16):')].replace('dolphin-si-query', 'dolphin-reset-code'), str(parent), 'exec'), globals())
values = [0, 1, 7, 8, 0x7fffffff, 0x80000000, 0xffffffff, 0x12345678]
for index in range(16):
    flag = 0 if index % 2 == 0 else 1 if index < 8 else 0x80000000
    value = values[index // 2]
    data[index * stride:index * stride + 16] = b'OSHSM_PPC_DLP001'
    struct.pack_into('>I', data, index * stride + 20, index)
    code.extend([dform(14, 0, 0, 0x2032), (31 << 26) | (146 << 1)])
    pointer(code, 0, 0xc200)
    code.append(spr(0, 1008, True))
    for register, value_register in [(1, 0x80540000), (2, 0x805335e0), (13, 0x8052e720),
            (30, 0xc0680000 + index * stride), (31, 0x55660000 + index)]:
        pointer(code, register, value_register)
    for address, word in [(0x80492240, flag), (0x80492244, value)]:
        pointer(code, 11, address)
        pointer(code, 0, word)
        code.append(dform(36, 0, 11, 0))
    call = base + len(code) * 4
    code.append(branch(call, 0x802194e0, True))
    code.extend([dform(36, 3, 30, 24), dform(36, 0, 30, 28), 0x7c0000a6, dform(36, 0, 30, 32)])
    for register, slot in [(1, 36), (2, 40), (13, 44), (30, 48), (31, 52)]:
        code.append(dform(36, register, 30, slot))
    code.extend([spr(0, 8, False), dform(36, 0, 30, 56)])
    for address, slot in [(0x80492240, 60), (0x80492244, 64), (0xcc003024, 68)]:
        pointer(code, 11, address)
        code.extend([dform(32, 0, 11, 0), dform(36, 0, 30, slot)])
    pointer(code, 0, 0xc001cafe)
    code.append(dform(36, 0, 30, 16))
    records.append({'index': index, 'flag': flag, 'value': value, 'call': call, 'return': call + 4})
halt = base + len(code) * 4
code.append(branch(halt, halt))
patches = []
exec(compile(source[source.index('while len(code) % 8:'):source.index('sha = lambda path:')], str(parent), 'exec'), globals())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'generation.json').write_text(json.dumps({'originalSha256': sha(original_path), 'harnessSha256': sha(output / 'fpr-init.dol'),
    'generatorSha256': sha(Path(__file__)), 'parentSha256': sha(parent), 'helperSha256': sha(helpers),
    'wrapperSha256': sha(experiment / 'run_reset_code_dolphin.ps1'), 'baseRunnerSha256': sha(experiment / 'run_dolphin_probe.ps1'),
    'records': records, 'patches': [], 'limits': ['Unpatched whole function, prepared reboot parameters/ABI/MSR2032; emulator cold-reset register.',
        'Extra final PI read is a laboratory snapshot; no physical reset event or intermediate bus proof.']}, indent=2) + '\n')
print('Generated16whole original reset-code calls:8cold/8warm parameter controls')

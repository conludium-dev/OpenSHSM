"""Execute the original suspend-counter decrement/gate on software750CL."""
from pathlib import Path
import hashlib
import json
import platform
import struct
import sys

assert platform.machine() == 'x86_64'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN
from unicorn import ppc_const as ppc

dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
header = struct.unpack('>64I', dol[:256])
start, size = 0x8021B0D0, 36
section = next(i for i in range(18) if header[18 + i] <= start and start + size <= header[18 + i] + header[36 + i])
offset = header[section] + start - header[18 + section]
fragment = dol[offset:offset + size]
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
uc.mem_write(start, fragment)
thread = 0x80568000
rows = []
for count in (0, 1, 2, 7, 0x7FFFFFFF):
    uc.reg_write(ppc.UC_PPC_REG_29, thread)
    uc.mem_write(thread + 0x2CC, struct.pack('>I', count))
    for step in range(12):
        pc = start if step == 0 else uc.reg_read(ppc.UC_PPC_REG_PC)
        if pc in (0x8021B0F4, 0x8021B324):
            break
        uc.emu_start(pc, 0x8021B0F4, count=1)
    pc = uc.reg_read(ppc.UC_PPC_REG_PC)
    result = struct.unpack('>I', uc.mem_read(thread + 0x2CC, 4))[0]
    assert result == max(0, count - 1)
    assert pc == (0x8021B0F4 if count == 1 else 0x8021B324)
    rows.append({'originalCount': count, 'newCount': result, 'nextPC': hex(pc)})
output = Path('work/private-game/static-recomp/stock-baseline/headless-scheduler-observe')
(output / 'original-suspend-gate.json').write_text(json.dumps({'result': 'ORIGINAL_SUSPEND_DECREMENT_GATE_PASS5',
    'dolSha256': sha(dol_path), 'fragmentSha256': hashlib.sha256(fragment).hexdigest(),
    'verifierSha256': sha(Path(__file__).resolve()), 'cases': rows,
    'limits': ['Own unmodified9instruction fragment on software750CL; counter decrease/gate only.',
        'Count1 alone reaches state-check gate, count0 clamps and other positive counts remain suspended.',
        'No full queue insertion/ResumeThread/scheduler/hardware or live stall-resolution proof.']}, indent=2) + '\n')
print('ORIGINAL_SUSPEND_DECREMENT_GATE_PASS5')

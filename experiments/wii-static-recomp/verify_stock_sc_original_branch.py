"""Original750CL cache loop and one erroneous post-callback branch, not full SC hardware handling."""
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
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
header = struct.unpack('>64I', dol[:256])
start, length = 0x80212FD0, 48
section = next(i for i in range(18) if header[18 + i] <= start and start + length <= header[18 + i] + header[36 + i])
offset = header[section] + start - header[18 + section]
fragment = dol[offset:offset + length]
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
uc.mem_write(start, fragment)
rows = []
for alignment in range(32):
    address = 0x80560000 + alignment
    uc.reg_write(ppc.UC_PPC_REG_3, address)
    uc.reg_write(ppc.UC_PPC_REG_4, 384)
    uc.reg_write(ppc.UC_PPC_REG_CTR, 123)
    uc.emu_start(start, 0x80212FF8, count=128)
    expected = address + ((384 + alignment + 31) // 32) * 32
    assert uc.reg_read(ppc.UC_PPC_REG_PC) == 0x80212FF8
    assert uc.reg_read(ppc.UC_PPC_REG_CTR) == 0 and uc.reg_read(ppc.UC_PPC_REG_3) == expected
    uc.emu_start(0x80212FF4, 0x80212FF8, count=1)
    assert uc.reg_read(ppc.UC_PPC_REG_CTR) == 0xFFFFFFFF
    assert uc.reg_read(ppc.UC_PPC_REG_PC) == 0x80212FEC
    rows.append({'alignment': alignment, 'completedAddress': expected, 'wrongResumeCTR': 0xFFFFFFFF, 'wrongResumePC': 0x80212FEC})
output = Path('work/private-game/static-recomp/stock-baseline/sc-resume-research')
(output / 'original-branch.json').write_text(json.dumps({'result': 'ORIGINAL_CACHE_AND_WRONG_RESUME_BRANCH_PASS32',
    'dolSha256': sha(dol_path), 'fragmentSha256': hashlib.sha256(fragment).hexdigest(),
    'verifierSha256': sha(Path(__file__)), 'cases': rows,
    'limits': ['Actual original loop executed only until SC, no original OS SC exception handler/hardware oracle.',
        'Wrong restored PC with CTR0 wraps on real BDNZ semantics; native callback selection is independently controlled.']}, indent=2) + '\n')
print('ORIGINAL_CACHE_AND_WRONG_RESUME_BRANCH_PASS32')

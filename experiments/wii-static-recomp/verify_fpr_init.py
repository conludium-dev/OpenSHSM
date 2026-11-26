"""Verify the original FPR initializer with poisoned registers; distinguish paired reference from PPC execution."""
from pathlib import Path
import hashlib
import json
import platform
import struct
import subprocess
import sys

assert platform.machine() == 'x86_64'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN
from unicorn import ppc_const as ppc

output = Path('work/private-game/static-recomp/mass-fpscr')
exe = output / 'openshsm-mass-boot'
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
dol = dol_path.read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = struct.unpack('>64I', dol[:256])
result = subprocess.run([str(exe), '--fpr-init-check', str(dol_path)], capture_output=True, text=True, timeout=30)
(output / 'fpr-init.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
rows = [list(map(int, line.split()[1:])) for line in result.stdout.splitlines()]
assert len(rows) == 8
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
for index in range(18):
    if header[36 + index]:
        uc.mem_write(header[18 + index], dol[header[index]:header[index] + header[36 + index]])
for mode, row in enumerate(rows):
    assert len(row) == 68 and row[:4] == [mode, 0x807f0000, 0x2000, 0]
    assert row[4:36] == [0] * 32
    prior_second = [struct.unpack('>Q', struct.pack('>d', -float((index + 1) * (mode + 1))))[0] for index in range(32)]
    assert row[36:] == (prior_second if mode < 4 else [0] * 32)
    if mode < 4:
        for index in range(32):
            uc.reg_write(getattr(ppc, 'UC_PPC_REG_' + str(index)), 0)
            uc.reg_write(getattr(ppc, 'UC_PPC_REG_FPR' + str(index)), struct.unpack('>Q', struct.pack('>d', float((index + 1) * (mode + 1))))[0])
        uc.reg_write(ppc.UC_PPC_REG_MSR, 0)
        uc.reg_write(ppc.UC_PPC_REG_13, 0x8052e720)
        uc.reg_write(ppc.UC_PPC_REG_FPSCR, 0x12345678)
        uc.reg_write(ppc.UC_PPC_REG_CR, 0)
        uc.reg_write(ppc.UC_PPC_REG_LR, 0x807f0000)
        uc.emu_start(0x80210890, 0x807f0000, count=128)
        actual = [uc.reg_read(ppc.UC_PPC_REG_PC), uc.reg_read(ppc.UC_PPC_REG_MSR), uc.reg_read(ppc.UC_PPC_REG_FPSCR)]
        actual += [uc.reg_read(getattr(ppc, 'UC_PPC_REG_FPR' + str(index))) for index in range(32)]
        assert actual == row[1:36], (mode, actual, row[1:36])
report = {'result': 'PASS_WITH_SCOPE_LIMITS', 'originalPpcNonPairedCases': 4, 'nativePairedReferenceCases': 4,
          'poisonedFprRegistersPerCase': 32, 'records': rows, 'executableSha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
          'scriptSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'limits': ['Original PSE=0 initializer executes in independent Unicorn; PS1 is not exposed by its API.',
                     'PSE=1 case verifies generated original control flow against documented zero psq_l/ps_mr semantics, not a second CPU implementation.',
                     'Full original startup sets PSE=1; independent whole-prefix proof remains blocked at paired singles.']}
(output / 'fpr-init.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS:4 original PSE=0 initializer cases;4 native paired-reference cases; full paired CPU oracle pending')

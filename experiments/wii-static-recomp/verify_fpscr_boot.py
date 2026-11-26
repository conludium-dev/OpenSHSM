"""Compare original bootstrap through FPR initialization, retaining the native function-PC limitation."""
from pathlib import Path
import hashlib
import json
import platform
import re
import struct
import sys

assert platform.machine() == 'x86_64'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn import ppc_const as ppc

output = Path('work/private-game/static-recomp/mass-fpscr')
boot = json.loads((output / 'boot.json').read_text())
assert boot['executableSha256'] == hashlib.sha256((output / 'openshsm-mass-boot').read_bytes()).hexdigest()
assert 'BOOT_BOUNDARY pc=802130e0 lr=802134ac msr=2000' in boot['stdout']
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = struct.unpack('>64I', dol[:256])
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
for index in range(18):
    if header[36 + index]:
        uc.mem_write(header[18 + index], dol[header[index]:header[index] + header[36 + index]])
for index in range(32):
    uc.reg_write(getattr(ppc, 'UC_PPC_REG_' + str(index)), 0)
    uc.reg_write(getattr(ppc, 'UC_PPC_REG_FPR' + str(index)), 0)
for register in (ppc.UC_PPC_REG_CR, ppc.UC_PPC_REG_LR, ppc.UC_PPC_REG_CTR, ppc.UC_PPC_REG_XER, ppc.UC_PPC_REG_MSR, ppc.UC_PPC_REG_FPSCR):
    uc.reg_write(register, 0)
states = {row[0]: row[1:] for row in [list(map(int, line.split()[1:])) for line in boot['stdout'].splitlines() if line.startswith('FP_STATE ')]}
trace, compared = [], []
def observe(_, address, size, __):
    trace.append(address)
    if address in states:
        cr = uc.reg_read(ppc.UC_PPC_REG_CR)
        actual = [uc.reg_read(ppc.UC_PPC_REG_FPSCR)] + [(cr >> ((7 - index) * 4)) & 15 for index in range(8)]
        actual += [uc.reg_read(getattr(ppc, 'UC_PPC_REG_FPR' + str(index))) for index in range(32)]
        assert actual == states[address][:41], (hex(address), actual, states[address][:41])
        compared.append(address)
uc.hook_add(UC_HOOK_CODE, observe)
uc.emu_start(0x80006310, 0x802108b0, count=1024)
assert uc.reg_read(ppc.UC_PPC_REG_PC) == 0x802108b0
entries = [int(value, 16) for value in re.findall(r'BOOT_TRACE address=([0-9a-f]+)', boot['stdout'])]
assert compared == entries[:8] and len(entries) == 11
assert 0x802108ac in trace
report = {'result': 'PARTIAL_VERIFICATION', 'originalInstructionsExecuted': len(trace), 'originalTrace': trace, 'nativeCallEntries': entries,
          'originalStopPC': '0x802108B0', 'nativeFunctionPC': '0x802130E0', 'nextBoundary': 'Native ICEnable; independent oracle lacks paired-single execution',
          'fprFpscrCrEntrySnapshotsMatch': len(compared),
          'bootReportSha256': hashlib.sha256((output / 'boot.json').read_bytes()).hexdigest(),
          'limits': ['Controlled zero-start fixture; no physical Wii trace or complete cache/OS/menu boot.',
                     'Native execution reaches HID0 ICE refusal but full prefix after psq_l is unverified: Unicorn raises UC_ERR_EXCEPTION there.',
                     'Native PC retains function entry on helper refusal; the actual mtspr is at 802130EC.',
                     'Unicorn does not expose PS1 registers via this API; PS1 native snapshots are retained but not independently verified here.',
                     'Zero FPSCR initialization agrees exactly; arbitrary FI/reserved-bit fidelity remains unresolved in separate mtfsf tests.']}
(output / 'boot-original-comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PARTIAL:', len(trace), 'original instructions;', len(compared), 'entry snapshots; paired-single oracle required')

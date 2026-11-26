"""Original OS consumer with controlled TBR responses and low-memory adjustment."""
from pathlib import Path
import hashlib
import itertools
import json
import platform
import struct
import subprocess
import sys

assert platform.machine() == 'x86_64'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn import ppc_const as ppc

output = Path('work/private-game/static-recomp/mass-timebase-active')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'os-time-build.json').read_text())
assert build['executableSha256'] == sha(output / 'os-time-probe')
assert build['probeHeaderSha256'] == sha(Path('experiments/wii-static-recomp/os_time_probe.h'))
values = [0, 1, 0xffffffff, 0x100000000, 0x7fffffffffffffff, 0x8000000000000000, 0xffffffff00000000, 0xffffffffffffffff]
cases = list(itertools.product(values, values))
result = subprocess.run([str(output / 'os-time-probe'), '--os-time-check'], input=''.join(f'{a} {b}\n' for a, b in cases),
                        capture_output=True, text=True, timeout=30)
assert result.returncode == 0, (result.returncode, result.stdout[-1000:], result.stderr)
rows = [list(map(int, line.split())) for line in result.stdout.splitlines()]
assert len(rows) == 64
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = struct.unpack('>64I', dol[:256])
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
for address, length in [(0x8021c030, 100), (0x8021c000, 24), (0x802174e0, 20), (0x80217520, 36)]:
    section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
    offset = header[section] + address - header[18 + section]
    uc.mem_write(address, dol[offset:offset + length])
uc.mem_write(0x8021c02c, struct.pack('>I', 0x7c0103a6))
uc.mem_write(0x807f0000, struct.pack('>II', 0x7cc102a6, 0x7ce000a6))
tick, pending, reads = 0, None, 0

def observe(_uc, address, size, data):
    global pending, reads
    if pending is not None:
        register, value = pending
        uc.reg_write(getattr(ppc, f'UC_PPC_REG_{register}'), value)
        pending = None
    if address in (0x8021c000, 0x8021c004, 0x8021c008):
        high = address != 0x8021c004
        register = {0x8021c000: 3, 0x8021c004: 4, 0x8021c008: 5}[address]
        pending = (register, tick >> 32 if high else tick & 0xffffffff)
        reads += 1

uc.hook_add(UC_HOOK_CODE, observe)
for (tick, adjustment), row in zip(cases, rows):
    pending, reads = None, 0
    registers = [0 if index < 14 else 0x12340000 + index * 0x100 for index in range(32)]
    registers[0], registers[1] = 0x20000000, 0x80540000
    for index, value in enumerate(registers):
        uc.reg_write(getattr(ppc, f'UC_PPC_REG_{index}'), value)
    uc.reg_write(ppc.UC_PPC_REG_MSR, 0x2030)
    uc.reg_write(ppc.UC_PPC_REG_CR, 0)
    uc.reg_write(ppc.UC_PPC_REG_LR, 0x807f0000)
    uc.mem_write(0x800030d8, struct.pack('>Q', adjustment))
    uc.emu_start(0x8021c02c, 0x807f0008, count=128)
    abi = int(uc.reg_read(ppc.UC_PPC_REG_1) == registers[1] and uc.reg_read(ppc.UC_PPC_REG_LR) == 0x807f0000)
    abi &= int(all(uc.reg_read(getattr(ppc, f'UC_PPC_REG_{index}')) == registers[index] for index in range(14, 32)))
    expected = [uc.reg_read(ppc.UC_PPC_REG_3), uc.reg_read(ppc.UC_PPC_REG_4), abi,
                uc.reg_read(ppc.UC_PPC_REG_7), uc.reg_read(ppc.UC_PPC_REG_6), uc.reg_read(ppc.UC_PPC_REG_CR), reads]
    assert uc.reg_read(ppc.UC_PPC_REG_PC) == 0x807f0008
    assert row == expected, (tick, adjustment, row, expected)
    assert (row[0] << 32 | row[1]) == (tick + adjustment) & ((1 << 64) - 1)
report = {'result': 'ORIGINAL_OS_TIME_ADJUSTMENT_ABI_CONTROLLED_MATCH', 'cases': 64,
          'buildSha256': sha(output / 'os-time-build.json'), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Controlled TBR responses and low-memory adjustment; no physical timebase/RTC/calendar or live full-OS timing proof.',
                     'MSR.EE=0 fixture only; interrupt-enabled restore/delivery remains unsupported.']}
(output / 'os-time-comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS original OS time consumer:64cases/64-bit addition-wrap/carry/MSR/ABI; live clock epoch unverified')

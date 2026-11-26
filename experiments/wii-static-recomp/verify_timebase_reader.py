"""Original HI/LO/HI consumer with controlled timebase responses, not a hardware clock oracle."""
from pathlib import Path
import hashlib
import json
import platform
import struct
import subprocess
import sys

assert platform.machine() == 'x86_64'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn import ppc_const as ppc

output = Path('work/private-game/static-recomp/mass-timebase')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
cases = []
mask = (1 << 64) - 1
for high in (0, 1, 0x7fffffff, 0x80000000, 0xffffffff):
    for low in (0, 1, 0x7fffffff, 0xfffffffe, 0xffffffff):
        first = (high << 32) | low
        second = (((high + 1) & 0xffffffff) << 32)
        third = (((high + 2) & 0xffffffff) << 32)
        cases += [[first, first, first], [first, second, second, second, second + 1, second],
                  [first, second, second, second, third, third, third, third + 1, third]]
request = ''.join(str(len(values)) + ' ' + ' '.join(map(str, values)) + '\n' for values in cases)
exe = output / 'openshsm-mass-boot'
native = subprocess.run([str(exe), '--clock-check'], input=request, capture_output=True, text=True, timeout=30)
assert native.returncode == 0, (native.returncode, native.stdout[-1000:], native.stderr)
rows = [list(map(int, line.split())) for line in native.stdout.splitlines()]
assert len(rows) == 75
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = struct.unpack('>64I', dol[:256])
address, size = 0x8021c000, 24
section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
offset = header[section] + address - header[18 + section]
code = dol[offset:offset + size]
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
uc.mem_write(address - 4, struct.pack('>I', 0x7c0103a6) + code)
uc.mem_write(0x807f0000, struct.pack('>I', 0x7cc102a6))
clock_values, clock_index, pending, retries = [], 0, None, 0

def observe(_uc, pc, size, data):
    global clock_index, pending, retries
    if pending is not None:
        register, value = pending
        uc.reg_write(getattr(ppc, f'UC_PPC_REG_{register}'), value)
        pending = None
    if pc in (address, address + 4, address + 8):
        opcode = struct.unpack_from('>I', code, pc - address)[0]
        ident = ((opcode >> 16) & 31) | (((opcode >> 11) & 31) << 5)
        assert opcode >> 26 == 31 and ((opcode >> 1) & 1023) == 371 and ident in (268, 269)
        assert clock_index < len(clock_values)
        value = clock_values[clock_index]
        clock_index += 1
        pending = ((opcode >> 21) & 31, (value >> 32) if ident == 269 else (value & 0xffffffff))
    if pc == address + 16:
        retries += int(not (uc.reg_read(ppc.UC_PPC_REG_CR) & 0x20000000))

uc.hook_add(UC_HOOK_CODE, observe)
for clock_values, row in zip(cases, rows):
    clock_index, pending, retries = 0, None, 0
    for index in range(32):
        uc.reg_write(getattr(ppc, f'UC_PPC_REG_{index}'), 0)
    uc.reg_write(ppc.UC_PPC_REG_0, 0x20000000)
    uc.reg_write(ppc.UC_PPC_REG_CR, 0)
    uc.reg_write(ppc.UC_PPC_REG_LR, 0x807f0000)
    uc.emu_start(address - 4, 0x807f0004, count=128)
    expected = [uc.reg_read(getattr(ppc, f'UC_PPC_REG_{index}')) for index in (3, 4, 5)]
    assert uc.reg_read(ppc.UC_PPC_REG_PC) == 0x807f0004
    expected += [0x807f0000, uc.reg_read(ppc.UC_PPC_REG_LR), clock_index, retries,
                 uc.reg_read(ppc.UC_PPC_REG_6), uc.reg_read(ppc.UC_PPC_REG_CR)]
    assert row == expected and clock_index == len(clock_values), (clock_values, row, expected)
for bad in ('', '0', '-1', '129', '3 1 2', '3 1 2 3 extra', '3 1 2 -1', '3 1 2 18446744073709551616'):
    result = subprocess.run([str(exe), '--clock-check'], input=bad + '\n', capture_output=True, text=True, timeout=5)
    assert result.returncode == 8
result = subprocess.run([str(exe), '--clock-check'], input='1 0\n', capture_output=True, text=True, timeout=5)
assert result.returncode == 3
report = {'result': 'ORIGINAL_TIMEBASE_RETRY_CONSUMER_CONTROLLED_MATCH', 'cases': 75, 'invalidInputGuards': 8,
          'exhaustionGuard': True, 'executableSha256': sha(exe), 'verifierSha256': sha(Path(__file__)),
          'loweringSha256': sha(output / 'lowering.json'),
          'limits': ['Original24-byte consumer executes with controlled TBL/TBU responses supplied by a disclosed instruction observer.',
                     'Tests original control flow, return/CR/XER and zero/one/two retries including32/64-bit rollover; not physical clock or mftb hardware semantics.',
                     'Native live monotonic policy/frequency/RTC epoch and whole original OS execution require separate acceptance.']}
(output / 'reader-comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS original controlled timebase consumer:75cases/retry0..2/32-64rollover/8input guards/exhaustion; live OS unverified')

"""Check HID2 policy separately from the independent original-PPC instruction oracle."""
from pathlib import Path
import hashlib
import itertools
import json
import platform
import struct
import subprocess
import sys

assert platform.machine() == 'x86_64', 'Use verified Rosetta PPC oracle'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
import unicorn
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN
from unicorn import ppc_const as ppc

output = Path('work/private-game/static-recomp/mass-processor')
exe = output / 'openshsm-mass-boot'
samples = [0, 0xffffffff, 0x0f000000, 0xa0000000, 0xf0ff0000, 0x0000ffff, 0x55555555, 0xaaaaaaaa]
cases = list(itertools.product(samples, samples, [0, 0x4000]))
cases += [(1 << bit, value, mode) for bit, value, mode in itertools.product(range(32), [0, 0xffffffff, 0xa0000000], [0, 0x4000])]
legal_values = [(index * 0x9e3779b9) & 0xf0ff0000 for index in range(256)]
cases += [(0, value, 0) for value in legal_values]
request = ''.join(f'{prior} {value} {mode}\n' for prior, value, mode in cases)
result = subprocess.run([str(exe), '--processor-check'], input=request, capture_output=True, text=True, timeout=60)
(output / 'register-check.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, (result.returncode, result.stderr[-3000:])
rows = [list(map(int, line.split())) for line in result.stdout.splitlines()]
assert len(rows) == len(cases)
records = []
for case, row in zip(cases, rows):
    prior, value, mode = case
    expected = prior if mode else (value & 0xf0ff0000) | (prior & 0x0f000000)
    assert row == [prior, value, mode, int(bool(mode)), expected, int(not mode)], (case, row, expected)
    records.append({'prior': prior, 'written': value, 'msr': mode, 'value': expected,
                    'scope': 'privilegeSafetyGuard' if mode else 'DolphinHid2RegisterPolicy', 'pass': True})

dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = struct.unpack('>64I', dol[:256])
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
for index in range(18):
    if header[36 + index]:
        uc.mem_write(header[18 + index], dol[header[index]:header[index] + header[36 + index]])
uc.reg_write(ppc.UC_PPC_REG_MSR, 0)
sentinel = 0x807f0000
for value, row in zip(legal_values, rows[-256:]):
    uc.reg_write(ppc.UC_PPC_REG_3, value)
    uc.reg_write(ppc.UC_PPC_REG_LR, sentinel)
    uc.emu_start(0x802107e0, sentinel, count=8)
    assert uc.reg_read(ppc.UC_PPC_REG_PC) == sentinel and uc.reg_read(ppc.UC_PPC_REG_3) == value
    uc.emu_start(0x802107d0, sentinel, count=8)
    assert uc.reg_read(ppc.UC_PPC_REG_PC) == sentinel and uc.reg_read(ppc.UC_PPC_REG_3) == row[4]
report = {'result': 'PASS', 'policyAndGuardCases': len(cases), 'originalPpcLegalWriteReadCases': 256, 'records': records,
          'executableSha256': hashlib.sha256(exe.read_bytes()).hexdigest(), 'dolSha256': hashlib.sha256(dol).hexdigest(),
          'scriptSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'oracleVersion': unicorn.__version__,
          'reference': 'https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/PowerPC/Interpreter/Interpreter_SystemRegisters.cpp',
          'policy': {'writableMask': '0xF0FF0000', 'preservedDmaQueueMask': '0x0F000000'},
          'limits': ['Reserved/DMA-queue write policy uses the separately inspected Dolphin reference, not unverified Unicorn hardware fidelity.',
                     'Independent original PPC execution covers legal writable-bit values with zero DMA queue; no physical Wii trace.',
                     'User-mode access aborts safely; original guest exception-vector delivery is not implemented.',
                     'DMA/locked-cache/gather-pipe consumers and hardware/cache initialization are not accepted by these register tests.']}
bad_inputs = ['x 0 0\n', '0 0\n', '0 0 0 extra\n', '-1 0 0\n', '4294967296 0 0\n', '0 0 0junk\n']
for bad_input in bad_inputs:
    rejected = subprocess.run([str(exe), '--processor-check'], input=bad_input, capture_output=True, text=True, timeout=10)
    assert rejected.returncode == 8 and not rejected.stdout, (bad_input, rejected.returncode, rejected.stdout)
report['invalidInputGuards'] = len(bad_inputs)
(output / 'register-check.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS:', len(cases), 'HID2 policy/guard cases;', 256, 'original PPC legal write/read cases; physical hardware unverified')

"""Compare mtfsf state changes with independent PPC execution, separating synthetic mask probes."""
from pathlib import Path
import hashlib
import json
import platform
import random
import struct
import subprocess
import sys

assert platform.machine() == 'x86_64', 'Use verified Rosetta PPC oracle'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
import unicorn
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN
from unicorn import ppc_const as ppc

output = Path('work/private-game/static-recomp/mass-fpscr')
exe = output / 'openshsm-mass-boot'
lowering = json.loads((output / 'lowering.json').read_text())
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = struct.unpack('>64I', dol[:256])
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
for index in range(18):
    if header[36 + index]:
        uc.mem_write(header[18 + index], dol[header[index]:header[index] + header[36 + index]])
randomizer = random.Random(0x5348534d)
samples = [0, 0xffffffff, 0x80000000, 0x60000000, 0x00000800, 0x01f80700, 0xaaaaaaaa, 0x55555555]
samples += [1 << bit for bit in range(32)] + [randomizer.getrandbits(32) for _ in range(64)]
cases, expected, records = [], [], []
for site in lowering['changes']:
    address, opcode = int(site['address'], 16), int(site['opcode'], 16)
    for value in samples:
        prior = randomizer.getrandbits(32)
        source = (randomizer.getrandbits(32) << 32) | value
        cr = randomizer.getrandbits(32)
        uc.reg_write(ppc.UC_PPC_REG_MSR, 0x2000)
        uc.reg_write(ppc.UC_PPC_REG_FPSCR, prior)
        actual_prior = uc.reg_read(ppc.UC_PPC_REG_FPSCR)
        uc.reg_write(ppc.UC_PPC_REG_CR, cr)
        uc.reg_write(getattr(ppc, 'UC_PPC_REG_FPR' + str(site['register'])), source)
        uc.emu_start(address, address + 4, count=1)
        cases.append((actual_prior, source, opcode, 0x2000, cr))
        expected.append([0, uc.reg_read(ppc.UC_PPC_REG_FPSCR), uc.reg_read(ppc.UC_PPC_REG_CR), source])
        records.append({'scope': 'originalDOLInstruction', 'address': hex(address), 'source': source, 'prior': actual_prior})
original_cases = len(cases)
for fields in range(256):
    for record in (0, 1):
        opcode = (0xfdfe058e & ~(255 << 17)) | (fields << 17) | record
        uc.mem_write(0x807e0000, struct.pack('>I', opcode))
        prior, source, cr = randomizer.getrandbits(32), randomizer.getrandbits(64), randomizer.getrandbits(32)
        uc.reg_write(ppc.UC_PPC_REG_MSR, 0x2000)
        uc.reg_write(ppc.UC_PPC_REG_FPSCR, prior)
        actual_prior = uc.reg_read(ppc.UC_PPC_REG_FPSCR)
        uc.reg_write(ppc.UC_PPC_REG_CR, cr)
        uc.reg_write(ppc.UC_PPC_REG_FPR0, source)
        uc.emu_start(0x807e0000, 0x807e0004, count=1)
        cases.append((actual_prior, source, opcode, 0x2000, cr))
        expected.append([0, uc.reg_read(ppc.UC_PPC_REG_FPSCR), uc.reg_read(ppc.UC_PPC_REG_CR), source])
        records.append({'scope': 'syntheticInstructionMaskAndRecordProbe', 'fields': fields, 'record': record})
request = ''.join(' '.join(map(str, case)) + '\n' for case in cases)
result = subprocess.run([str(exe), '--fpscr-check'], input=request, capture_output=True, text=True, timeout=60)
(output / 'fpscr-check.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, (result.returncode, result.stderr[-3000:])
rows = [list(map(int, line.split())) for line in result.stdout.splitlines()]
assert len(rows) == len(cases)
divergences = []
for case, row, wanted, record in zip(cases, rows, expected, records):
    prior, source, opcode, msr, cr = case
    mask = sum(15 << (4 * bit) for bit in range(8) if (opcode >> 17) & (1 << bit))
    reference = ((prior & ~mask) | (source & mask)) & 0xfffff7ff
    reference &= ~0x60000000
    if reference & 0x01f80700:
        reference |= 0x20000000
    if (reference >> 22) & (reference & 0xf8):
        reference |= 0x40000000
    reference_cr = ((cr & ~0x0f000000) | (((reference >> 28) & 15) << 24)) if opcode & 1 else cr
    assert row == [0, reference, reference_cr, source], (case, row, reference, reference_cr)
    difference = row[1] ^ wanted[1]
    assert row[0] == wanted[0] and row[2:] == wanted[2:] and not (difference & ~0x20800), (case, row, wanted, record)
    if difference:
        divergences.append({'case': record, 'nativeFpscr': row[1], 'unicornFpscr': wanted[1], 'differentBits': hex(difference)})
guards = [(0x12345678, 0, 0xfdfe058e, 0, 0xabcdef01), (0, 0x01000080, 0xfdfe058e, 0x2900, 0xabcdef01)]
for case in guards:
    result = subprocess.run([str(exe), '--fpscr-check'], input=' '.join(map(str, case)) + '\n', capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and list(map(int, result.stdout.split())) == [1, case[0], case[4], case[1]], result.stdout
bad = ['0 0\n', '-1 0 0 0 0\n', '4294967296 0 0 0 0\n', '0 18446744073709551616 0 0 0\n',
       '0 0 0 0 0\n', '0 0 4261283214 8192 0 extra\n', '0 0 4261283214 8192 0junk\n']
for value in bad:
    result = subprocess.run([str(exe), '--fpscr-check'], input=value, capture_output=True, text=True, timeout=10)
    assert result.returncode == 8 and not result.stdout, (value, result.returncode, result.stdout)
report = {'result': 'PASS', 'originalInstructionCases': original_cases, 'syntheticMaskRecordCases': len(cases) - original_cases,
          'refusalCases': len(guards), 'malformedInputCases': len(bad), 'records': records,
          'oracleDivergences': divergences, 'exactUnicornCases': len(cases) - len(divergences),
          'executableSha256': hashlib.sha256(exe.read_bytes()).hexdigest(), 'oracleVersion': unicorn.__version__,
          'scriptSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'limits': ['Independent instruction-state oracle, not physical Wii traces.',
                     'Unicorn keeps reserved bit 0x800 and clears FI 0x20000; Dolphin-derived policy differs. All divergences are retained; hardware fidelity of these bits is unresolved.',
                     'Rounding/non-IEEE modes are stored; later arithmetic consumers are not verified by mtfsf tests.',
                     'Guest FP exception-vector delivery is unavailable and aborts before state mutation.']}
(output / 'fpscr-check.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS reference policy:', original_cases, 'original mtfsf cases;', len(cases) - original_cases,
      'synthetic mask/Rc probes;', len(cases) - len(divergences), 'exact Unicorn matches;', len(divergences), 'retained FI/reserved divergences')

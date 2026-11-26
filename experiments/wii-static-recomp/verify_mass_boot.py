"""Verify original entrypoint prefix to the first strict processor-register boundary."""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import re
import struct
import sys

assert platform.machine() == 'x86_64', 'Use verified Rosetta Unicorn PPC runtime'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn import ppc_const as ppc

parser = argparse.ArgumentParser()
parser.add_argument('--processor', action='store_true')
parser.add_argument('--cache', action='store_true')
args = parser.parse_args()
args.processor |= args.cache
output = Path('work/private-game/static-recomp/mass-processor' if args.processor else 'work/private-game/static-recomp/mass-current')
if args.cache:
    output = Path('work/private-game/static-recomp/mass-cache')
boot = json.loads((output / 'boot.json').read_text())
assert boot['result'] == 'BLOCKED_AT_ORIGINAL_BOOT' and boot['exitCode'] == 7
assert boot['executableSha256'] == hashlib.sha256((output / 'openshsm-mass-boot').read_bytes()).hexdigest()
boundary = re.search(r'BOOT_BOUNDARY pc=([0-9a-f]+) lr=([0-9a-f]+) msr=([0-9a-f]+)', boot['stdout'])
expected_boundary = 0x802130d0 if args.processor else 0x802107d0
if args.cache:
    expected_boundary = 0x80210890
assert boundary and int(boundary[1], 16) == expected_boundary
registers = list(map(int, re.search(r'BOOT_REGISTERS((?: \d+){32})', boot['stdout'])[1].split()))
stack_bytes = bytes(map(int, re.search(r'BOOT_STACK((?: \d+){64})', boot['stdout'])[1].split()))
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
words = struct.unpack('>64I', dol[:256])
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
for index in range(18):
    if words[36 + index]:
        uc.mem_write(words[18 + index], dol[words[index]:words[index] + words[36 + index]])
for index in range(32):
    uc.reg_write(getattr(ppc, 'UC_PPC_REG_' + str(index)), 0)
for register in (ppc.UC_PPC_REG_CR, ppc.UC_PPC_REG_LR, ppc.UC_PPC_REG_CTR, ppc.UC_PPC_REG_XER, ppc.UC_PPC_REG_MSR):
    uc.reg_write(register, 0)
trace = []
uc.hook_add(UC_HOOK_CODE, lambda _, address, size, __: trace.append(address))
uc.emu_start(0x80006310, int(boundary[1], 16), count=1024)
assert uc.reg_read(ppc.UC_PPC_REG_PC) == int(boundary[1], 16)
assert uc.reg_read(ppc.UC_PPC_REG_LR) == int(boundary[2], 16)
assert uc.reg_read(ppc.UC_PPC_REG_MSR) == int(boundary[3], 16)
assert [uc.reg_read(getattr(ppc, 'UC_PPC_REG_' + str(index))) for index in range(32)] == registers
assert uc.mem_read(registers[1] + 16 - 32, 64) == stack_bytes
entries = [int(value, 16) for value in re.findall(r'BOOT_TRACE address=([0-9a-f]+)', boot['stdout'])]
expected_entries = [0x80006310, 0x80006480, 0x800065c0, 0x80211ca0, 0x802107d0]
if args.processor:
    expected_entries += [0x802107e0, 0x802130d0]
if args.cache:
    expected_entries += [0x80210890]
assert entries == expected_entries
assert all(address in trace for address in entries[:-1])
report = {'result': 'PASS', 'scope': 'Original startup instruction prefix matches native until strict register boundary; not game boot.',
          'entry': '0x80006310', 'boundary': f'0x{expected_boundary:08X}', 'processorRegister': 'HID0/SPR1008' if args.processor else 'HID2/SPR920',
          'originalInstructionsExecuted': len(trace), 'originalTrace': trace, 'nativeCallEntries': entries,
          'registersLrMsrPcStackMatch': True, 'dolSha256': hashlib.sha256(dol).hexdigest(),
          'bootReportSha256': hashlib.sha256((output / 'boot.json').read_bytes()).hexdigest(),
          'limits': ['Controlled zeroed CPU/MMU fixture, not original Wii power-on register state or physical console trace.',
                     'HID2 instruction intentionally not executed; native backend hardcoded read-zero is not accepted as source behavior.',
                     'No FPR/cache/OS/IOS/GX/disc/audio/controller initialization, original menu or scene reached.']}
if args.processor:
    count = len(trace)
    uc.reg_write(ppc.UC_PPC_REG_LR, 0x807f0000)
    uc.emu_start(0x802107d0, 0x807f0000, count=16)
    original_hid2 = uc.reg_read(ppc.UC_PPC_REG_3)
    native_hid2 = int(re.search(r'BOOT_PROCESSOR hid2=([0-9a-f]+)', boot['stdout'])[1], 16)
    assert original_hid2 == native_hid2 == 0xa0000000
    report['originalInstructionsExecuted'] = count
    report['originalTrace'] = trace[:count]
    report['hid2OriginalReadback'] = original_hid2
    report['limits'][1] = 'Original HID2 read/write executed for zero-start A0000000 bootstrap transition; arbitrary reserved-bit policy checked against separate Dolphin reference, not assumed from Unicorn.'
if args.cache:
    assert 'BOOT_CACHE hid0=0 invalidations=1' in boot['stdout']
    report['processorRegister'] = 'FPR/FPSCR initialization'
    report['cacheInvalidations'] = 1
    report['limits'].append('HID0 ICFI self-clear and immutable-code validation are separate reference/PC-adapter checks; Unicorn prefix is not physical cache-fidelity proof.')
(output / 'boot-original-comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS:', report['originalInstructionsExecuted'], 'original entrypoint instructions match native; next blocker', report['processorRegister'])

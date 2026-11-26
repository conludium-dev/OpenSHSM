"""Compare the complete recompiled IOS_Open wrapper with original PPC and explicit service fixtures."""
from pathlib import Path
import hashlib
import itertools
import json
import platform
import re
import struct
import subprocess
import sys
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--original-allocator', action='store_true')
parser.add_argument('--original-free', action='store_true')
args = parser.parse_args()
args.original_allocator |= args.original_free

assert platform.machine() == 'x86_64', 'Use the verified Rosetta PPC oracle runtime'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn import ppc_const as ppc

output = Path('work/private-game/static-recomp/ios-open-free' if args.original_free else
              'work/private-game/static-recomp/ios-open-allocator' if args.original_allocator else
              'work/private-game/static-recomp/ios-open-wrapper')
output.mkdir(exist_ok=True)
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
dol = dol_path.read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = struct.unpack('>64I', dol[:256])
sections = [(header[i], header[18 + i], header[36 + i]) for i in range(18) if header[36 + i]]
source = Path('work/private-game/static-recomp/mass-current/output_67.cpp')
text = source.read_text()
start = text.index('void func_80242550(CPUContext& ctx) {')
end = text.index('\nvoid func_', start + 1)
body = text[start:end]
markers = re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', body)
for pc, word in markers:
    pc = int(pc, 16)
    assert 0x80242550 <= pc < 0x80242674
    offset, base, _ = next(row for row in sections if row[1] <= pc < row[1] + row[2])
    assert struct.unpack_from('>I', dol, offset + pc - base)[0] == int(word, 16)
assert {int(pc, 16) for pc, _ in markers} == set(range(0x80242550, 0x80242674, 4)) - {0x802425FC}
if args.original_allocator:
    for entry in (('80243570', '802438A0', '802438B0') if args.original_free else ('80243570', '802438A0')):
        start = text.index(f'void func_{entry}(CPUContext& ctx) {{')
        end = text.index('\nvoid func_', start + 1)
        body += '\n' + text[start:end]
    markers = re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', body)
    expected_addresses = (set(range(0x80242550, 0x80242674, 4)) - {0x802425FC})
    expected_addresses |= set(range(0x80243570, 0x8024389C, 4)) | {0x802438A0}
    if args.original_free:
        expected_addresses |= set(range(0x802438B0, 0x80243A98, 4)) - {0x80243964}
    assert {int(pc, 16) for pc, _ in markers} == expected_addresses
    for pc, word in markers:
        pc = int(pc, 16)
        offset, base, _ = next(row for row in sections if row[1] <= pc < row[1] + row[2])
        assert struct.unpack_from('>I', dol, offset + pc - base)[0] == int(word, 16)
generated = output / 'selected.cpp'
generated.write_text('#include "runtime/cpu_context.h"\n#include <iostream>\nusing namespace nwii::runtime;\n'
                     'void func_802438A0(CPUContext&);\nvoid func_80212FD0(CPUContext&);\nvoid func_802421F0(CPUContext&);\n'
                     'void func_802174E0(CPUContext&);\nvoid func_80217520(CPUContext&);\n' + body)
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime/include')
host = Path('experiments/wii-static-recomp/ios_open_host.cpp')
exe = output / 'ios-open-host'
build = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit', '-I', str(upstream),
                        *(['-DSHSM_ORIGINAL_ALLOCATOR'] if args.original_allocator else []),
                        *(['-DSHSM_ORIGINAL_FREE'] if args.original_free else []),
                        str(host), str(generated), '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'build.log').write_text(build.stdout + build.stderr)
assert build.returncode == 0, build.stderr[-3000:]
cases = list(itertools.product([0, 1, 20, 63, 64, 65], [0, 1], [0, 1], [1, 0xFFFFFFFF], [0, 0x80000000]))
native = subprocess.run([str(exe.resolve())], input=''.join(' '.join(map(str, case)) + '\n' for case in cases),
                        capture_output=True, text=True, timeout=60)
(output / 'native.log').write_text(native.stdout + native.stderr)
assert native.returncode == 0, native.stderr[-3000:]
rows = [line.split() for line in native.stdout.splitlines()]
assert len(rows) == len(cases)
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
uc.mem_map(0x93E00000, 0x10000)
for offset, base, size in sections:
    uc.mem_write(base, dol[offset:offset + size])
registers = [getattr(ppc, f'UC_PPC_REG_{i}') for i in range(32)]
events = []
allocation = 0
covered = set()


def observe(machine, address, size, data):
    if address in (0x807F0100, 0x807F0104):
        return
    if args.original_allocator and address in (0x802174E0, 0x80217520):
        events.extend([3, 0, 0, 0] if address == 0x802174E0 else [4, uc.reg_read(registers[3]), 0, 0])
        if address == 0x802174E0:
            uc.reg_write(registers[3], 0)
        uc.reg_write(ppc.UC_PPC_REG_PC, uc.reg_read(ppc.UC_PPC_REG_LR))
        return
    if address in ((0x80212FD0, 0x802421F0) if args.original_allocator else (0x802438A0, 0x80212FD0, 0x802421F0)):
        arguments = [uc.reg_read(registers[i]) for i in (3, 4, 5)]
        if address == 0x802438A0:
            events.extend([0, *arguments])
            uc.reg_write(registers[3], allocation)
        elif address == 0x80212FD0:
            events.extend([1, *arguments[:2], 0])
        else:
            events.extend([2, *arguments[:2], 0])
            uc.reg_write(registers[3], 0xFFFFFFFA)
        uc.reg_write(ppc.UC_PPC_REG_PC, uc.reg_read(ppc.UC_PPC_REG_LR))
        return
    assert 0x80242550 <= address < 0x80242674 or (args.original_allocator and
           (0x80243570 <= address < 0x8024389C or address == 0x802438A0)) or (
            args.original_free and 0x802438B0 <= address < 0x80243A98), hex(address)
    covered.add(address)


uc.hook_add(UC_HOOK_CODE, observe)
records = []
for case, row in zip(cases, rows):
    length, region, fail, mode, xer = case
    packet, path = (0x93E01000, 0x93E02000) if region else (0x806A0000, 0x806A1000)
    allocation = 0 if fail else packet
    uc.mem_write(packet, bytes([0xA5]) * 64)
    uc.mem_write(path, b'A' * length + bytes(96 - length))
    uc.mem_write(0x806FFFC0, bytes(96))
    uc.mem_write(0x80528B74, struct.pack('>I', 3))
    if args.original_allocator:
        uc.mem_write(packet, bytes([0xA5]) * 4096)
        uc.mem_write(0x804B2B40, bytes(128))
        uc.reg_write(registers[1], 0x80700000)
        uc.reg_write(registers[3], packet)
        uc.reg_write(registers[4], 64 if fail else 4096)
        uc.reg_write(ppc.UC_PPC_REG_LR, 0x807F0000)
        uc.emu_start(0x80243570, 0x807F0000, count=2000)
        assert uc.reg_read(ppc.UC_PPC_REG_PC) == 0x807F0000 and uc.reg_read(registers[3]) == 0
        uc.mem_write(0x80528B74, bytes(4))
        uc.mem_write(0x806FFF80, bytes(160))
    for i, register in enumerate(registers):
        uc.reg_write(register, 0x12340000 + i)
    for i, value in ((1, 0x80700000), (3, path), (4, mode), (13, 0x8052E720)):
        uc.reg_write(registers[i], value)
    for register, value in ((ppc.UC_PPC_REG_LR, 0x807F0000), (ppc.UC_PPC_REG_CTR, 0),
                            (ppc.UC_PPC_REG_XER, xer), (ppc.UC_PPC_REG_CR, 0)):
        uc.reg_write(register, value)
    uc.mem_write(0x807F0100, struct.pack('>I', 0x7FE103A6))
    uc.reg_write(registers[31], xer)
    uc.emu_start(0x807F0100, 0x807F0104, count=1)
    uc.reg_write(registers[31], 0x1234001F)
    events.clear()
    uc.emu_start(0x80242550, 0x807F0000, count=2000)
    if args.original_free:
        for cycle in range(2):
            if cycle:
                uc.reg_write(registers[3], path)
                uc.reg_write(registers[4], mode)
                uc.reg_write(ppc.UC_PPC_REG_LR, 0x807F0000)
                uc.emu_start(0x80242550, 0x807F0000, count=2000)
            result = uc.reg_read(registers[3])
            assert uc.reg_read(ppc.UC_PPC_REG_PC) == 0x807F0000 and result == (0xFFFFFFEA if fail else 0xFFFFFFFA)
            pointer = 0 if fail else events[-3]
            events.extend([6, result, cycle, 0])
            if not fail:
                assert pointer == packet + 32
                events.extend([5, pointer, 0, 0])
                uc.reg_write(registers[3], 0)
                uc.reg_write(registers[4], pointer)
                uc.reg_write(ppc.UC_PPC_REG_LR, 0x807F0000)
                uc.emu_start(0x802438B0, 0x807F0000, count=2000)
                assert uc.reg_read(ppc.UC_PPC_REG_PC) == 0x807F0000 and uc.reg_read(registers[3]) == 0
                assert struct.unpack('>I', uc.mem_read(0x804B2B44, 4))[0] == 0
                assert struct.unpack('>I', uc.mem_read(0x804B2B4C, 4))[0] == packet
                assert struct.unpack('>I', uc.mem_read(packet + 4, 4))[0] == 4080
    final_pc = uc.reg_read(ppc.UC_PPC_REG_PC)
    saved31 = uc.reg_read(registers[31])
    uc.mem_write(0x807F0104, struct.pack('>I', 0x7FE102A6))
    uc.emu_start(0x807F0104, 0x807F0108, count=1)
    observed_xer = uc.reg_read(registers[31])
    uc.reg_write(registers[31], saved31)
    uc.reg_write(ppc.UC_PPC_REG_PC, final_pc)
    state = [uc.reg_read(reg) for reg in (ppc.UC_PPC_REG_PC, ppc.UC_PPC_REG_LR, ppc.UC_PPC_REG_CTR,
                                         ppc.UC_PPC_REG_XER, ppc.UC_PPC_REG_CR)]
    state += [uc.reg_read(reg) for reg in registers]
    state[3] = observed_xer
    expected = state + [len(events)] + events
    suffix_size = 4 if args.original_allocator else 2
    actual = list(map(int, row[:-suffix_size]))
    packet_hex, stack_hex = bytes(uc.mem_read(packet, 64)).hex(), bytes(uc.mem_read(0x806FFFC0, 96)).hex()
    suffix = [packet_hex, stack_hex]
    if args.original_allocator:
        suffix += [bytes(uc.mem_read(packet, 4096)).hex(), bytes(uc.mem_read(0x804B2B40, 128)).hex()]
    assert actual == expected and row[-suffix_size:] == suffix, (case, actual, expected, 'memoryMatches', row[-suffix_size:] == suffix)
    assert state[0] == 0x807F0000
    assert state[8] == (0xFFFFFFEA if fail else 0 if args.original_free else 0xFFFFFFFA)
    if args.original_allocator:
        assert events[:8] == [3, 0, 0, 0, 4, 0, 0, 0]
        if not fail:
            assert events[8:12] == [1, path, min(length, 64) + 1, 0]
            assert events[12:16] == [2, packet + 32, 0, 0]
        elif not args.original_free:
            assert len(events) == 8
    else:
        assert events[:4] == [0, 3, 64, 32]
    if not fail and not args.original_allocator:
        assert events[4:8] == [1, path, min(length, 64) + 1, 0]
        assert events[8:12] == [2, packet, 0, 0]
        assert struct.unpack_from('>I', bytes.fromhex(packet_hex), 12)[0] == (path - 0x80000000) & 0xFFFFFFFF
    records.append({'input': case, 'events': list(events), 'memory': suffix, 'state': state})
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = {'result': f'IOS_OPEN_{"ORIGINAL_FREE_REUSE" if args.original_free else "ORIGINAL_ALLOCATOR" if args.original_allocator else "COMPLETE_WRAPPER"}_NATIVE_ORIGINAL{len(cases)}_CASES_PASS', 'cases': records,
          'originalAllocator': args.original_allocator,
          'originalFree': args.original_free,
          'openCalls': len(cases) * (2 if args.original_free else 1),
          'successfulFreeCalls': sum(not case[2] for case in cases) * 2 if args.original_free else 0,
          'comparedMemoryBytesPerCase': 64 + 96 + (4096 + 128 if args.original_allocator else 0),
          'instructionMarkers': len(markers), 'coveredOriginalAddresses': [hex(pc) for pc in sorted(covered)],
          'dolSha256': sha(dol_path), 'generatedSourceSha256': sha(generated), 'parentGeneratedSha256': sha(source),
          'hostSourceSha256': sha(host), 'executableSha256': sha(exe), 'scriptSha256': sha(Path(__file__)),
          'limits': [('Original heap creation/aligned allocator execute; interrupt/cache/transport services are explicit fixtures.' if args.original_allocator else
                      'Allocator/cache-flush/transport are explicit synthetic services, not original implementations.'),
                     'Synthetic mtxer/mfxer setup/readback avoids known Unicorn XER API flag mismatch; original function bytes unchanged.',
                     'Transport returns supplied -6; no actual IOSKernel/device/MMIO/thread/IRQ coupling.',
                     'MEM2 values are synthetic inputs; actual SHSM loader/allocation remains unmeasured.',
                     'MMU uses uncached fixture backing; no cache visibility, physical Wii or full boot proof.',
                     ('Free mode tests two host-directed allocation/free cycles; original transport does not free requests here, fragmentation/invalid pointers unverified.' if args.original_free else
                      'Allocator mode tests one allocation in a fresh 4096/64byte heap; free/reuse/fragmentation/general invalid inputs unverified.'),
                     'Full original function entry/return, GPR/CR/XER/LR/CTR/packet/stack/service order compared; no FPU instructions.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'PASS IOS_Open {"with original free/reuse" if args.original_free else "with original heap/allocator" if args.original_allocator else "wrapper"}: {len(cases)} native/original cases; actual IOS services remain unverified')

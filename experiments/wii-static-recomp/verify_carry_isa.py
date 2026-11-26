"""Original DOL subfic single-step oracle, including flag preservation and register aliases."""
from pathlib import Path
import hashlib
import itertools
import json
import platform
import struct
import subprocess
import sys
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--stock-carry', action='store_true')
parser.add_argument('--locked-cache', action='store_true')
parser.add_argument('--quantization', action='store_true')
args = parser.parse_args()
assert not args.locked_cache or args.stock_carry
assert not args.quantization or args.locked_cache

assert platform.machine() == 'x86_64', 'Use existing isolated x64 Unicorn setup'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN
from unicorn import ppc_const as ppc

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/stock-baseline/window-hid2-carry' if args.stock_carry else 'work/private-game/static-recomp/mass-carry')
if args.locked_cache:
    output = output.parent / 'window-locked-cache'
if args.quantization:
    output = output.parent / 'window-quantization'
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
lowering = json.loads(((output.parent / 'window-hid2-carry' if args.locked_cache else output) / 'lowering.json').read_text())
selected = {}
records = [{'changes': lowering['carryChanges']}] if args.stock_carry else lowering['records']
for record in records:
    for change in record['changes']:
        opcode = int(change['opcode'], 16)
        destination, source = (opcode >> 21) & 31, (opcode >> 16) & 31
        selected.setdefault((opcode >> 26, opcode & 65535, destination == source, source == 0, destination == 0), change)
instructions = list(selected.values())
exe = output / ('carry-isa-probe' if args.stock_carry else 'carry-probe')
if args.stock_carry:
    build = json.loads((output / 'carry-isa-build.json').read_text())
    assert sha(exe) == build['executableSha256'] and sha(experiment / 'carry_probe.cpp') == build['sourceSha256']
    marker = '#define main unused_frontend_main\n#include "memory_frontend_probe.cpp"\n#undef main'
    assert (experiment / 'carry_probe.cpp').read_text().replace(marker, '#include <iostream>') == (output / 'carry-isa-probe.cpp').read_text()
    assert sha(output / 'carry-isa-probe.cpp') == build['compiledSourceSha256']
else:
    result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit',
                         '-I', str(upstream / 'nWiiRuntime/include'), str(experiment / 'carry_probe.cpp'),
                         str(experiment / 'processor_adapter.cpp'), '-o', str(exe)], capture_output=True, text=True, timeout=30)
    (output / 'isa-build.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
cases = list(itertools.product(range(len(instructions)),
                               [0, 1, 2, 127, 255, 256, 32767, 32768, 0x7fffffff, 0x80000000, 0xfffffffe, 0xffffffff],
                               [0, 0x20000000, 0x40000000, 0x80000000, 0xe000007f]))
request = ''.join(f"{int(instructions[index]['opcode'], 16)} {value} {xer}\n" for index, value, xer in cases)
result = subprocess.run([str(exe)], input=request, capture_output=True, text=True, timeout=30)
assert result.returncode == 0, result.stderr
rows = [list(map(int, line.split())) for line in result.stdout.splitlines()]
assert len(rows) == len(cases)
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
header = struct.unpack('>64I', dol[:256])
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
for change in instructions:
    address = int(change['address'], 16)
    section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
    offset = header[section] + address - header[18 + section]
    code = dol[offset:offset + 4]
    assert struct.unpack('>I', code)[0] == int(change['opcode'], 16)
    uc.mem_write(address, code)
carry_mismatches = 0
api_readback_mismatches = 0
for (index, value, xer), row in zip(cases, rows):
    change = instructions[index]
    opcode, address = int(change['opcode'], 16), int(change['address'], 16)
    destination, source = (opcode >> 21) & 31, (opcode >> 16) & 31
    registers = [0x12340000 + register * 0x100 for register in range(32)]
    registers[source] = value
    scratch = next(register for register in range(32) if register not in (source, destination))
    registers[scratch] = xer
    for register, initial in enumerate(registers):
        uc.reg_write(getattr(ppc, f'UC_PPC_REG_{register}'), initial)
    setup = (31 << 26) | (scratch << 21) | (1 << 16) | (467 << 1)
    observe = (31 << 26) | (scratch << 21) | (1 << 16) | (339 << 1)
    uc.mem_write(address - 4, struct.pack('>III', setup, opcode, observe))
    uc.reg_write(ppc.UC_PPC_REG_CR, 0xaaaaaaaa)
    uc.emu_start(address - 4, address + 8, count=3)
    observed_xer = uc.reg_read(getattr(ppc, f'UC_PPC_REG_{scratch}'))
    api_readback_mismatches += int(observed_xer != uc.reg_read(ppc.UC_PPC_REG_XER))
    expected = [uc.reg_read(getattr(ppc, f'UC_PPC_REG_{destination}')), observed_xer,
                uc.reg_read(ppc.UC_PPC_REG_CR), 1]
    assert row == expected, (change, value, hex(xer), row, expected)
    for register, initial in enumerate(registers):
        if register not in (destination, scratch):
            assert uc.reg_read(getattr(ppc, f'UC_PPC_REG_{register}')) == initial
    assert uc.reg_read(ppc.UC_PPC_REG_PC) == address + 8
    carry_mismatches += int((xer ^ expected[1]) & 0x20000000 != 0)
assert carry_mismatches > 0
report = {'result': 'ORIGINAL_IMMEDIATE_CARRY_RESULT_XER_CR_ALIAS_MATCH', 'classes': len(instructions), 'cases': len(cases),
          'oldUnchangedCarryMismatchCases': carry_mismatches, 'sites': len(lowering['carryChanges']) if args.stock_carry else lowering['sites'],
          'unicornApiXerReadbackMismatchCases': api_readback_mismatches,
          'loweringSha256': sha((output.parent / 'window-hid2-carry' if args.locked_cache else output) / 'lowering.json'), 'adapterSha256': sha(experiment / 'carry_adapter.h'),
          'sourceSha256': sha(experiment / 'carry_probe.cpp'), 'executableSha256': sha(exe), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Original subfic/addic/addic. instruction equivalence with synthetic PPC mtxer setup/mfxer observation; Unicorn API-only XER access gave inconsistent flag state/readback.',
                     'Not every PPC arithmetic instruction or full-function CFG proof.',
                     'Class selection covers actual DOL immediates/alias patterns; test inputs cover selected boundary values, not all uint32 inputs.']}
(output / 'isa-comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'PASS original immediate carry:{len(instructions)}classes/{len(cases)}cases/result/XER/CR/aliases; unchanged carry mismatches:{carry_mismatches}')

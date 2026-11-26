"""Execute actual original rotate-record opcodes against the exact corrected generated snippets."""
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
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN
from unicorn import ppc_const as ppc

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/mass-bat')
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
lowering = json.loads((output / 'lowering.json').read_text())
selected = {}
for record in lowering['records']:
    for change in record['changes']:
        if change['kind'] != 'rotate-record':
            continue
        opcode = int(change['opcode'], 16)
        selected.setdefault((opcode >> 26, (opcode >> 1) & 0x7fff, ((opcode >> 21) & 31) == ((opcode >> 16) & 31)), change)
instructions = list(selected.values())
assert instructions
code = '#include "runtime/cpu_context.h"\n#include <bit>\n#include <iostream>\nusing nwii::runtime::CPUContext;\nvoid run(unsigned index, CPUContext& ctx) {\n    switch (index) {\n'
for index, instruction in enumerate(instructions):
    code += f'    case {index}: {{\n' + instruction['after'] + '        break;\n    }\n'
code += '''    default: throw std::runtime_error("bad case");
    }
}
int main() {
    CPUContext ctx;
    unsigned index, sourceValue, destinationValue, xer, cr;
    while (std::cin >> index >> sourceValue >> destinationValue >> xer >> cr) {
        unsigned opcode;
        if (!(std::cin >> opcode)) { return 8; }
        const unsigned source = (opcode >> 21) & 31, destination = (opcode >> 16) & 31;
        for (unsigned reg = 0; reg < 32; ++reg) { ctx.gpr[reg] = 0x12340000 + reg * 0x100; }
        ctx.gpr[destination] = destinationValue;
        ctx.gpr[source] = sourceValue;
        const auto registers = ctx.gpr;
        ctx.xer = xer;
        for (unsigned field = 0; field < 8; ++field) {
            const auto bits = (cr >> (28 - field * 4)) & 15;
            ctx.cr[field].lt = bits & 8; ctx.cr[field].gt = bits & 4;
            ctx.cr[field].eq = bits & 2; ctx.cr[field].so = bits & 1;
        }
        run(index, ctx);
        bool preserved = true;
        for (unsigned reg = 0; reg < 32; ++reg) { if (reg != destination) { preserved &= ctx.gpr[reg] == registers[reg]; } }
        unsigned resultCr = 0;
        for (const auto& field : ctx.cr) {
            resultCr = (resultCr << 4) | ((field.lt ? 8 : 0) | (field.gt ? 4 : 0) | (field.eq ? 2 : 0) | (field.so ? 1 : 0));
        }
        std::cout << ctx.gpr[destination] << ' ' << ctx.xer << ' ' << resultCr << ' ' << preserved << '\\n';
    }
}
'''
source = output / 'rotate-record-probe.cpp'
source.write_text(code)
exe = output / 'rotate-record-probe'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-I', str(upstream / 'nWiiRuntime/include'), str(source), '-o', str(exe)],
                        capture_output=True, text=True, timeout=30)
(output / 'rotate-build.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
cases = list(itertools.product(range(len(instructions)), [0, 1, 31, 0x12345678, 0x7fffffff, 0x80000000, 0xaaaaaaaa, 0xffffffff],
                               [0, 0xffffffff], [0, 0x80000000, 0xe000007f], [0xaaaaaaaa, 0x55555555]))
request = ''.join(f'{index} {value} {destination} {xer} {cr} {int(instructions[index]["opcode"], 16)}\n' for index, value, destination, xer, cr in cases)
result = subprocess.run([str(exe)], input=request, capture_output=True, text=True, timeout=30)
assert result.returncode == 0, result.stderr
rows = [list(map(int, line.split())) for line in result.stdout.splitlines()]
assert len(rows) == len(cases)
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = struct.unpack('>64I', dol[:256])
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
old_mismatches = 0
for (index, value, destination_value, xer, cr), row in zip(cases, rows):
    instruction = instructions[index]
    opcode, address = int(instruction['opcode'], 16), int(instruction['address'], 16)
    section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
    assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == opcode
    source_register, destination = (opcode >> 21) & 31, (opcode >> 16) & 31
    registers = [0x12340000 + reg * 0x100 for reg in range(32)]
    registers[destination] = destination_value
    registers[source_register] = value
    scratch = next(reg for reg in range(32) if reg not in (source_register, destination))
    registers[scratch] = xer
    for reg, initial in enumerate(registers):
        uc.reg_write(getattr(ppc, f'UC_PPC_REG_{reg}'), initial)
    setup = (31 << 26) | (scratch << 21) | (1 << 16) | (467 << 1)
    observe = (31 << 26) | (scratch << 21) | (1 << 16) | (339 << 1)
    uc.mem_write(address - 4, struct.pack('>III', setup, opcode, observe))
    uc.reg_write(ppc.UC_PPC_REG_CR, cr)
    uc.emu_start(address - 4, address + 8, count=3)
    observed_xer = uc.reg_read(getattr(ppc, f'UC_PPC_REG_{scratch}'))
    expected = [uc.reg_read(getattr(ppc, f'UC_PPC_REG_{destination}')), observed_xer, uc.reg_read(ppc.UC_PPC_REG_CR), 1]
    assert row == expected, (instruction, value, destination_value, xer, hex(cr), row, expected)
    for reg, initial in enumerate(registers):
        if reg not in (scratch, destination):
            assert uc.reg_read(getattr(ppc, f'UC_PPC_REG_{reg}')) == initial
    old_mismatches += bool(((cr >> 28) ^ (expected[2] >> 28)) & 1)
assert old_mismatches > 0
report = {'result': 'ORIGINAL_ROTATE_RECORD_RESULT_XER_CR_ALIAS_MATCH', 'classes': len(instructions), 'cases': len(cases),
          'oldPreservedSoMismatchCases': old_mismatches, 'sites': lowering['rotateRecordSites'],
          'loweringSha256': sha(output / 'lowering.json'), 'generatedProbeSha256': sha(source), 'executableSha256': sha(exe),
          'verifierSha256': sha(Path(__file__)),
          'limits': ['Exact corrected generated snippets versus actual original DOL op20/21 record instructions with PPC mtxer/mfxer observers.',
                     'Selected immediate/alias classes and boundary inputs; not all uint32 values or all PPC record-form instructions.',
                     'Full OS/boot/MMU behavior requires separate original runtime comparisons.']}
(output / 'rotate-comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'PASS original rotate-record:{len(instructions)}classes/{len(cases)}cases; oldSO mismatches:{old_mismatches}')

"""Original PPC single-step oracle for each transformed BO/BI/link/absolute class."""
from pathlib import Path
import hashlib
import itertools
import json
import platform
import struct
import subprocess
import sys

sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
assert platform.machine() == 'x86_64', 'Run this verifier under the existing isolated x64 Unicorn environment'
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN
from unicorn import ppc_const as ppc

output = Path('work/private-game/static-recomp/mass-branch')
experiment = Path('experiments/wii-static-recomp')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
lowering = json.loads((output / 'lowering.json').read_text())
classes = {}
for record in lowering['records']:
    for change in record['changes']:
        classes.setdefault(int(change['opcode'], 16) & 0x03ff0003, change)
selected = list(classes.values())
source = output / 'branch-predicate-probe.cpp'
text = '''#include <array>
#include <cstdint>
#include <iostream>
struct Field { bool lt, gt, eq, so; };
struct Context {
    uint32_t ctr = 0, lr = 0, pc = 0, inst_count = 1, callbacks = 0;
    std::array<Field, 8> cr{};
    bool suspend = false, taken = false;
};
bool process_pending_callbacks(Context& ctx) {
    ++ctx.callbacks;
    if (ctx.suspend) { throw 1; }
    return false;
}
'''
for index, change in enumerate(selected):
    body = change['after'].replace(f"goto loc_{int(change['target'], 16):08X};", '{ ctx.taken = true; return; }')
    text += f'void probe_{index}(Context& ctx) {{\n' + body + '    ++ctx.inst_count;\n}\n'
text += 'int main() {\nunsigned id, ctr, cr, lr, suspend;\nwhile (std::cin >> id >> ctr >> cr >> lr >> suspend) {\n'
text += 'Context ctx; ctx.ctr = ctr; ctx.lr = lr; ctx.suspend = suspend;\n'
text += 'for (unsigned i = 0; i < 8; ++i) { ctx.cr[i] = {bool(cr & (1u << (31-i*4))), bool(cr & (1u << (30-i*4))), bool(cr & (1u << (29-i*4))), bool(cr & (1u << (28-i*4)))}; }\n'
text += 'unsigned request = 0; try { switch(id) {\n'
for index in range(len(selected)):
    text += f'case {index}: probe_{index}(ctx); break;\n'
text += 'default: return 3; } } catch (int) { request = 1; }\n'
text += 'std::cout << id << " " << ctx.ctr << " " << ctx.lr << " " << ctx.callbacks << " " << ctx.taken << " " << request << "\\n";\n} }\n'
source.write_text(text)
exe = output / 'branch-predicate-probe'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', str(source), '-o', str(exe)], capture_output=True, text=True, timeout=60)
(output / 'isa-probe-build.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
cases = list(itertools.product(range(len(selected)), [0, 1, 2, 0x7fffffff, 0x80000000, 0xffffffff],
                               [0, 0xffffffff, 0xaaaaaaaa, 0x55555555], [0, 1]))
request = ''.join(f'{index} {ctr} {cr} 305419896 {suspend}\n' for index, ctr, cr, suspend in cases)
result = subprocess.run([str(exe)], input=request, capture_output=True, text=True, timeout=30)
assert result.returncode == 0, result.stderr
rows = [list(map(int, line.split())) for line in result.stdout.splitlines()]
assert len(rows) == len(cases)
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
for change in selected:
    uc.mem_write(int(change['address'], 16), struct.pack('>I', int(change['opcode'], 16)))
seen = set()
for (index, ctr, cr, suspend), row in zip(cases, rows):
    change = selected[index]
    address, target = int(change['address'], 16), int(change['target'], 16)
    uc.reg_write(ppc.UC_PPC_REG_CTR, ctr)
    uc.reg_write(ppc.UC_PPC_REG_CR, cr)
    uc.reg_write(ppc.UC_PPC_REG_LR, 305419896)
    uc.emu_start(address, address + 4, count=1)
    next_pc = uc.reg_read(ppc.UC_PPC_REG_PC)
    taken = int(next_pc == target)
    assert next_pc in (target, address + 4)
    assert row[:3] == [index, uc.reg_read(ppc.UC_PPC_REG_CTR), uc.reg_read(ppc.UC_PPC_REG_LR)], (change, row)
    assert row[3:] == [taken, int(taken and not suspend), int(taken and suspend)], (change, row)
    assert uc.reg_read(ppc.UC_PPC_REG_CR) == cr
    seen.add(taken)
assert seen == {0, 1}
report = {'result': 'ORIGINAL_BC_ORACLE_AND_CALLBACK_PATH_MATCH', 'classes': len(selected), 'cases': len(cases),
          'sitesCoveredByCheckedTemplates': lowering['sites'], 'loweringSha256': sha(output / 'lowering.json'),
          'verifierSha256': sha(Path(__file__)), 'sourceSha256': sha(source), 'executableSha256': sha(exe),
          'limits': ['Extracted generated branch snippets, original PPC single-step oracle; not full CFG/function equivalence.',
                     'Simulated callback request tests only call placement; actual scheduler/interrupt delivery/resume remains unavailable.']}
(output / 'isa-comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'PASS original BC oracle:{len(selected)}classes/{len(cases)}cases/taken and untaken/CTR/LR/strict callback paths')

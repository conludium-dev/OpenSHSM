"""Verify every regenerated sthbrx statement against original words and RAM semantics."""
from pathlib import Path
import hashlib
import json
import re
import shlex
import subprocess
from stock_psq_patch import lower_indexed
from stock_byte_reverse_patch import lower_byte_reverse, pattern

project = Path('.').resolve()
root = project / 'work/private-game/static-recomp/stock-baseline'
output = root / 'window-byte-reverse'
build = root / 'export/build'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
manifest = json.loads((output / 'build.json').read_text())
dol = (project / 'work/private-game/disc/DATA/sys/main.dol').read_bytes()
functions = []
entries = []
for module in manifest['modules']:
    original = root / 'export' / f'output_{module["index"]}.cpp'
    text, psq_sites = lower_indexed(original.read_text(), dol)
    corrected, sites = lower_byte_reverse(text, dol)
    assert sites == module['reverseSites'] and psq_sites == module['sites']
    assert (output / original.name).read_text() == corrected
    assert sha(output / f'{original.name}.o') == module['objectSha256']
    for match in pattern.finditer(text):
        word = int(match[3], 16)
        if (word >> 16) & 31:
            continue
        rb = (word >> 11) & 31
        rs = (word >> 21) & 31
        assert rs != rb
        statement = match[4].replace(f'ctx.mmu.write16(ctx.gpr[0] + ctx.gpr[{rb}],', f'ctx.mmu.write16(ctx.gpr[{rb}],')
        name = f'case_{len(entries)}'
        functions.append(f'void {name}(nwii::runtime::CPUContext& ctx) {{\n{statement}}}\n')
        entries.append(f'{{{name}, {rs}, {rb}}}')
assert len(entries) == 29
prefix = (project / 'experiments/wii-static-recomp/stock_psq_contract.cpp').read_text().split('int main() {')[0]
source = output / 'byte-reverse-contract.cpp'
source.write_text(prefix + '\n'.join(functions) + '''
struct Case { void (*run)(nwii::runtime::CPUContext&); unsigned rs, rb; };
int main() {
    nwii::runtime::CPUContext ctx;
    Case cases[] = {''' + ','.join(entries) + '''};
    unsigned count = 0;
    for (const auto& test : cases) {
        for (uint32_t base : {0x80000000u, 0x90000000u, 0xC0000000u, 0xD0000000u}) {
            for (uint32_t value : {0u, 1u, 0x1234u, 0x8000u, 0xFFFFu, 0x12345678u}) {
                const uint32_t address = base + 0x8000;
                ctx.gpr[0] = 0x1234;
                ctx.gpr[test.rb] = address;
                ctx.gpr[test.rs] = value;
                const auto before = ctx.gpr;
                ctx.mmu.write16(address - 2, 0x5A5A);
                ctx.mmu.write16(address, 0xA5A5);
                ctx.mmu.write16(address + 2, 0x3C3C);
                test.run(ctx);
                assert(ctx.mmu.read8(address) == (value & 255));
                assert(ctx.mmu.read8(address + 1) == ((value >> 8) & 255));
                assert(ctx.mmu.read16(address - 2) == 0x5A5A);
                assert(ctx.mmu.read16(address + 2) == 0x3C3C);
                assert(ctx.gpr == before);
                ++count;
            }
        }
    }
    std::cout << "PASS " << count << " actual generated sthbrx/R0/alias/data/canary cases\\n";
}
''')
flags = (build / 'CMakeFiles/OpenSHSMStockBaseline.dir/flags.make').read_text()
compiler = re.search(r'# compile CXX with (.+)', flags)[1]
arguments = []
for name in ('CXX_DEFINES', 'CXX_INCLUDES', 'CXX_FLAGS'):
    arguments += shlex.split(re.search(r'^' + name + r' = (.*)$', flags, re.M)[1])
probe = output / 'byte-reverse-contract'
subprocess.run([compiler, *arguments, '-I', str(output), str(source), '-o', str(probe)], check=True, timeout=60)
result = subprocess.run([str(probe)], capture_output=True, text=True, timeout=20)
assert result.returncode == 0, result.stdout + result.stderr
for name, digest in manifest['retainedGuestObjects'].items():
    assert sha(build / name) == digest
assert sha(root / 'ipc-cpbp/libnwiiruntime.a') == manifest['archiveSha256']
assert sha(output / 'OpenSHSMStockByteReverse') == manifest['executableSha256']
run_path = root / 'window-byte-reverse-headless-windowed-endian40-result.json'
run = json.loads(run_path.read_text()) if run_path.exists() else None
if run:
    assert run['executableSha256'] == manifest['executableSha256']
    log = root / 'window-byte-reverse-headless-windowed-endian40.log'
    assert sha(log) == run['logSha256']
(output / 'byte-reverse-audit.json').write_text(json.dumps({
    'result': 'GENERATED_STHBRX_ADDRESS_CONTRACT_PASS', 'sitesIncludingDuplicates': len(entries),
    'uniqueAddresses': len({site['address'] for module in manifest['modules'] for site in module['reverseSites']}),
    'contract': result.stdout.strip(), 'run': run,
    'limits': ['RAM contract uses actual emitted statements/actual MMU with trapping host stubs.',
        'DOL/DTK and Dolphin source corroborate original RA-zero semantics; no live Wii oracle.',
        'Whole startup/capture and absence of allocator corruption require separate inspection.']
}, indent=2) + '\n')
print(result.stdout.strip())

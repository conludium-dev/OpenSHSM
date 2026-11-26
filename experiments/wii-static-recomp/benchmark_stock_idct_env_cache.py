"""Compare isolated captured IDCT replay, not whole-game FPS or Wii equivalence."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'observer-env-research/idct-benchmark'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
original = public / 'stock_idct_replay.cpp'
text = original.read_text()
assert text.count('if (argc != 3)') == 1
text = text.replace('if (argc != 3)', 'if (argc != 4)')
text = '#include <array>\n#include <chrono>\n' + text
marker = '    for (unsigned range = 0; range < ranges; ++range) {'
assert text.count(marker) == 1
text = text.replace(marker, '    std::vector<std::pair<uint32_t, std::vector<uint8_t>>> snapshots;\n' + marker)
marker = '        for (size_t i = 0; i < data.size(); i += 2) {'
text = text.replace(marker, '        std::vector<uint8_t> bytes;\n' + marker)
marker = '            ctx.mmu.get_ptr(address)[i / 2] = uint8_t(std::stoul(data.substr(i, 2), nullptr, 16));'
assert text.count(marker) == 1
text = text.replace(marker, marker + '\n            bytes.push_back(ctx.mmu.get_ptr(address)[i / 2]);')
marker = '    ctx.pc = entry;\n    const uint32_t caller = ctx.lr;'
assert text.count(marker) == 1
text = text.replace('        }\n    }\n' + marker, '        }\n        snapshots.emplace_back(address, bytes);\n    }\n' + marker)
start = text.index('    if (entry == 0x8020AFD0) {')
end = text.index('    std::cout << "IDCT_REPLAY', start)
call = text[start:end]
text = text[:start] + '''    ctx.hid2 = 0xA0000000u;
    ctx.msr = (ctx.msr | 0x2000u) & ~0x8000u;
    const auto saved_msr = ctx.msr, saved_ctr = ctx.ctr, saved_xer = ctx.xer, saved_fpscr = ctx.fpscr;
    const auto saved_gpr = ctx.gpr;
    const auto saved_gqr = ctx.gqr;
    const auto saved_fpr = ctx.fpr, saved_ps1 = ctx.ps1;
    const auto saved_cr = ctx.cr;
    const auto saved_mem1 = ctx.mmu.mem1;
    const auto saved_mem2 = ctx.mmu.mem2;
    const auto saved_locked_cache = ctx.mmu.locked_cache;
    uint64_t reference_digest = 0;
    std::vector<uint8_t> reference_output;
    int64_t ns = 0;
    for (unsigned iteration = 0; iteration < 500; ++iteration) {
        ctx.pc = entry; ctx.lr = caller; ctx.msr = saved_msr;
        ctx.ctr = saved_ctr; ctx.xer = saved_xer; ctx.fpscr = saved_fpscr;
        ctx.gpr = saved_gpr;
        ctx.gqr = saved_gqr;
        ctx.fpr = saved_fpr;
        ctx.ps1 = saved_ps1;
        ctx.cr = saved_cr;
        ctx.mmu.mem1 = saved_mem1;
        ctx.mmu.mem2 = saved_mem2;
        ctx.mmu.locked_cache = saved_locked_cache;
        if (setjmp(ctx.exception_jmp_buf) != 0) { return 11; }
        const auto started = std::chrono::steady_clock::now();
''' + call + '''        if (ctx.pc != caller) { return 9; }
        ns += std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now() - started).count();
        uint64_t digest = 14695981039346656037ull;
        std::vector<uint8_t> current_output;
        for (const auto& [address, bytes] : snapshots) {
            for (size_t i = 0; i < bytes.size(); ++i) {
                const auto value = ctx.mmu.get_ptr(address)[i];
                current_output.push_back(value);
                digest = (digest ^ value) * 1099511628211ull;
            }
        }
        if (iteration == 0) {
            reference_digest = digest;
            reference_output = current_output;
        }
        if (digest != reference_digest || current_output != reference_output) { return 10; }
    }
    std::ofstream output_file(argv[3], std::ios::binary);
    output_file.write(reinterpret_cast<const char*>(reference_output.data()), reference_output.size());
    if (!output_file) { return 12; }
    std::cout << "IDCT_BENCHMARK iterations=500 ns=" << std::dec << ns
        << " digest=" << std::hex << reference_digest << std::dec << "\\n";
''' + text[end:]
source, obj = output / 'benchmark.cpp', output / 'benchmark.cpp.o'
source.write_text(text)
record = json.loads((root / 'window-fp-guard/output_37.cpp.record.json').read_text())
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
fixtures = sorted(root.glob('window-idct-fixtures-blocks120-thp-block*.txt'))
assert len(fixtures) == 3
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
executables = {}
for name, directory in [('baseline', 'headless-tev-banks'), ('corrected', 'headless-observer-env-cache')]:
    base_path = root / directory / 'build.json'
    base = json.loads(base_path.read_text())
    command = list(base['linkCommand'])
    command[command.index(str(root / 'headless-tev-banks/main.cpp.o'))] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
    command.insert(1, str(obj))
    exe = output / (name + '-benchmark')
    command[command.index('-o') + 1] = str(exe)
    subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=180)
    executables[name] = {'path': exe, 'sha256': sha(exe), 'baseBuildSha256': sha(base_path)}
rows = []
dol = Path('work/private-game/disc/DATA/sys/main.dol').resolve()
for fixture in fixtures:
    results = []
    outputs = []
    for iteration in range(3):
        for name in (('baseline', 'corrected') if iteration % 2 == 0 else ('corrected', 'baseline')):
            raw_output = output / (fixture.stem + f'-{name}-{iteration}.bin')
            result = subprocess.run([str(executables[name]['path']), str(dol), str(fixture), str(raw_output)], env=env,
                capture_output=True, text=True, timeout=60)
            log = output / (fixture.stem + f'-{name}-{iteration}.log')
            log.write_text(result.stdout + result.stderr)
            assert result.returncode == 0, (name, fixture.name, result.returncode, result.stdout, result.stderr[-2000:])
            match = re.search(r'IDCT_BENCHMARK iterations=500 ns=(\d+) digest=([0-9a-f]+)', result.stdout)
            assert match
            outputs.append(raw_output.read_bytes())
            results.append({'variant': name, 'nanoseconds': int(match[1]), 'digest': match[2],
                'outputSha256': sha(raw_output), 'logSha256': sha(log)})
    assert len({row['digest'] for row in results}) == 1
    assert all(value == outputs[0] for value in outputs)
    rows.append({'fixture': fixture.name, 'fixtureSha256': sha(fixture), 'results': results})
(output / 'comparison.json').write_text(json.dumps({'result': 'CAPTURED_IDCT_ENV_CACHE_IDENTICAL_500_REPLAYS',
    'originalReplaySourceSha256': sha(original), 'benchmarkSourceSha256': sha(source), 'benchmarkObjectSha256': sha(obj),
    'verifierSha256': sha(Path(__file__).resolve()), 'dolSha256': sha(dol),
    'executables': {name: {key: value for key, value in row.items() if key != 'path'} for name, row in executables.items()},
    'fixtures': rows, 'limits': ['Three captured native inputs,500isolated repeats each,three alternating baseline/corrected passes.',
        'HID2 paired enable, MSR.FP enabled and MSR.EE disabled are explicit fixture policy; not original lazy-FPU lifecycle/IRQ/whole video execution.',
        'Each iteration restores all backed native MMU RAM, outside timed interval; native function time includes callback checks.',
        'Whole seven captured memory ranges deterministic/equal, not complete original MMU/CPU behavior oracle.']}, indent=2) + '\n')
print('CAPTURED_IDCT_ENV_CACHE_IDENTICAL_500_REPLAYS')

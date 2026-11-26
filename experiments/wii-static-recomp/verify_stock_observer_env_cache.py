"""Compare actual IDCT observer output and getenv counts with fixed startup flags."""
from pathlib import Path
import hashlib
import json
import subprocess
from stock_observer_env_patch import idct

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'observer-env-research'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base_path = root / 'headless-tev-banks/build.json'
base = json.loads(base_path.read_text())
original = root / 'window-fp-guard/output_37.cpp'
record = json.loads((root / 'window-fp-guard/output_37.cpp.record.json').read_text())
assert sha(original) == record['sourceSha256']
prefix = original.read_text().split('#include "functions.h"', 1)[0]
assert 'ctx.mmu.write' not in prefix
fixture = '''
#include "processor_adapter.h"
#include <cassert>
#include <memory>
static bool test_enabled;
static unsigned test_calls;
char* stock_test_getenv(const char*) {
    ++test_calls;
    static char value[] = "1";
    return test_enabled ? value : nullptr;
}
int main(int argc, char** argv) {
    assert(argc == 3);
    test_enabled = std::string(argv[1]) == "on";
    const bool fixed = std::string(argv[2]) == "corrected";
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    ctx.gpr[2] = 0x8052B5E0;
    ctx.gpr[13] = 0x80500000;
    ctx.pc = 0x8020AFD0;
    ctx.mmu.write8(0x80560000, 17);
    for (unsigned i = 0; i < 50; ++i) {
        observe_idct(ctx, 0x8020AFD0, i < 10, 0x80560000);
    }
    assert(ctx.pc == 0x8020AFD0 && ctx.gpr[2] == 0x8052B5E0 && ctx.gpr[13] == 0x80500000);
    assert(ctx.mmu.read8(0x80560000) == 17);
    assert(test_calls == (fixed ? 1 : 50));
    std::cout << "OBSERVER_ENV_CALLS " << test_calls << '\\n';
}
'''
command = list(base['linkCommand'])
command[command.index(str(root / 'headless-tev-banks/main.cpp.o'))] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
results = {}
for name, transform in [('baseline', lambda text: text), ('corrected', idct)]:
    source, obj = output / (name + '.cpp'), output / (name + '.cpp.o')
    text = transform(prefix).replace('std::getenv("NWII_THPDUMP")', 'stock_test_getenv("NWII_THPDUMP")')
    source.write_text('char* stock_test_getenv(const char*);\n' + text + fixture)
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
        '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
    (output / (name + '-compile.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-2000:]
    cmd = list(command)
    cmd.insert(1, str(obj))
    exe = output / (name + '-probe')
    cmd[cmd.index('-o') + 1] = str(exe)
    subprocess.run(cmd, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
    results[name] = {}
    for flag in ('off', 'on'):
        result = subprocess.run([str(exe), flag, name], capture_output=True, timeout=30)
        assert result.returncode == 0, result.stderr[-2000:]
        (output / (name + '-' + flag + '.log')).write_bytes(result.stdout + result.stderr)
        results[name][flag] = result.stderr
    results[name]['executableSha256'] = sha(exe)
for flag in ('off', 'on'):
    assert results['baseline'][flag] == results['corrected'][flag]
assert results['corrected']['off'] == b''
assert results['corrected']['on'].count(b'[IDCTState]') == 38
(output / 'comparison.json').write_text(json.dumps({'result': 'IDCT_ENV_CACHE_OUTPUT_IDENTICAL_CALLS50_TO1',
    'baseBuildSha256': sha(base_path), 'originalSourceSha256': sha(original), 'verifierSha256': sha(Path(__file__).resolve()),
    'executables': {name: row['executableSha256'] for name, row in results.items()},
    'limits': ['Actual observer helper, controlled getenv provider, startup flag off/on in separate processes.',
        '50 calls per mode: disabled no records, enabled same38capped records; sampled guest fields unchanged.',
        'Does not test live environment mutation; per-process immutable diagnostic flags are intentional.',
        'No FPS/Wii hardware/full CPU or decoder equivalence claim.']}, indent=2) + '\n')
print('IDCT_ENV_CACHE_OUTPUT_IDENTICAL_CALLS50_TO1')

"""Check exact-index partition equivalence and reuse native runtime contracts/late endpoints with changed master only."""
from pathlib import Path
import hashlib
import json
import random
import struct
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-dispatch-o2'
public = Path('experiments/wii-static-recomp').resolve()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
parent_path = root / 'window-scheduler-o2/build.json'
parent = json.loads(parent_path.read_text())
assert sha(parent_path) == build['parentBuildSha256']
restored = Path(build['masterSourcePath']).read_text()
assert restored.startswith(build['includeAddition'])
restored = restored[len(build['includeAddition']):]
for before, after in reversed(build['masterPatches']):
    assert restored.count(after) == 1
    restored = restored.replace(after, before, 1)
assert restored == Path(build['masterOriginalPath']).read_text()
assert '#pragma clang optimize off' in restored and '#pragma clang optimize off' in Path(build['masterSourcePath']).read_text()
assert sha(Path(build['masterObjectPath'])) == build['masterObjectSha256']
assert sha(Path(build['helperObjectPath'])) == build['helperObjectSha256']
expected = list(parent['linkCommand'])
old_master = next(arg for arg in expected if Path(arg).name == 'fixed.cpp.o')
expected[expected.index(old_master)] = build['masterObjectPath']
expected.insert(1, build['helperObjectPath'])
expected[expected.index('-o') + 1] = build['executablePath']
assert expected == build['linkCommand']
assert all(arg in build['compileCommands'][0] for arg in ('-O2', '-ffp-contract=off', '-fno-strict-aliasing', '-fwrapv'))
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
temporary = Path(tempfile.mkdtemp(prefix='openshsm-dispatch-tests-', dir='/private/tmp'))
addresses = [record[0] for record in build['routeRecords']]
assert all(a <= b for a, b in zip(addresses, addresses[1:]))
first = {}
for index, address in enumerate(addresses):
    first.setdefault(address, index)
boundaries = sorted({0, 1 << 32, *first, *(address + 1 for address in first)})
queries = {}
for low, high in zip(boundaries, boundaries[1:]):
    for target in (low, high - 1, low + (high - low) // 2):
        queries[target] = first.get(target, len(addresses))
randomizer = random.Random(0x5348534D)
for _ in range(4096):
    target = randomizer.getrandbits(32)
    queries[target] = first.get(target, len(addresses))
table_path = temporary / 'addresses.bin'
query_path = temporary / 'queries.bin'
table_path.write_bytes(b''.join(struct.pack('<I', address) for address in addresses))
query_path.write_bytes(b''.join(struct.pack('<II', target, index) for target, index in queries.items()))
source = temporary / 'probe.cpp'
reference = build['masterPatches'][1][0]
reference = reference.replace('static void(*lookup_dispatch(uint32_t target))(CPUContext&)', 'static size_t reference_lookup(uint32_t target)')
reference = reference.replace('sizeof(g_dispatch_routes) / sizeof(g_dispatch_routes[0])', 'g_dispatch_routes.size()')
reference = reference.replace('return g_dispatch_routes[first].function;', 'return first;').replace('return nullptr;', 'return g_dispatch_routes.size();')
source.write_text('''#include "stock_dispatch_lookup.h"
#include <cstdio>
#include <vector>
#if defined(__clang__)
#pragma clang optimize off
#endif
static std::vector<StockDispatchRoute> g_dispatch_routes;
''' + reference + '''
int main(int argc, char** argv) {
    if (argc != 3) { return 1; }
    FILE* table = std::fopen(argv[1], "rb");
    FILE* queries = std::fopen(argv[2], "rb");
    if (!table || !queries) { return 2; }
    uint32_t address;
    while (std::fread(&address, 4, 1, table) == 1) { g_dispatch_routes.push_back({address, nullptr}); }
    std::fclose(table);
    uint32_t values[2];
    size_t count = 0;
    while (std::fread(values, sizeof(values), 1, queries) == 1) {
        if (reference_lookup(values[0]) != values[1] ||
            stock_dispatch_index(g_dispatch_routes.data(), g_dispatch_routes.size(), values[0]) != values[1]) { return 3; }
        ++count;
    }
    std::fclose(queries);
    const StockDispatchRoute duplicates[] = {{0, nullptr}, {7, nullptr}, {7, nullptr}, {UINT32_MAX, nullptr}};
    if (stock_dispatch_index(nullptr, 0, 123) != 0 || stock_dispatch_index(duplicates, 4, 7) != 1 ||
        stock_dispatch_index(duplicates, 4, UINT32_MAX) != 3 || stock_dispatch_index(duplicates, 4, 8) != 4) { return 4; }
    std::printf("EXACT_ORIGINAL_ROUTE_PARTITIONS_EQUAL %zu\\n", count);
}
''')
sdk = build['compileCommands'][1][build['compileCommands'][1].index('-isysroot') + 1]
exe = temporary / 'probe'
compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', '-isysroot', sdk,
    '-std=c++20', '-O0', '-I', str(public), str(source), build['helperObjectPath'], '-o', str(exe)],
    capture_output=True, text=True, timeout=60)
assert compiled.returncode == 0, compiled.stderr[-2500:]
run = subprocess.run([str(exe), str(table_path), str(query_path)], capture_output=True, text=True, timeout=30)
assert run.returncode == 0 and f'EXACT_ORIGINAL_ROUTE_PARTITIONS_EQUAL {len(queries)}' in run.stdout, run.stdout + run.stderr
(output / 'route-verification.json').write_text(json.dumps({
    'result': 'ORIGINAL_EXACT_ROUTE_INDEX_PARTITION_REPRESENTATIVES_EQUAL',
    'buildSha256': sha(build_path), 'routes': len(addresses), 'uniqueAddresses': len(first),
    'fullUint32Partitions': len(boundaries) - 1, 'queries': len(queries),
    'querySha256': sha(query_path), 'tableSha256': sha(table_path), 'sourceSha256': sha(source),
    'executablePath': str(exe), 'executableSha256': sha(exe), 'verifierSha256': sha(Path(__file__)),
    'limits': ['Start/end/midpoint representatives of every key/gap partition plus4096 random queries, not enumeration of all2^32 addresses.',
        'Expected index from independent first-address map, original lower_bound code retained in probe, synthetic duplicate/empty/uint32 extremes tested.',
        'Master table/pointer selection and every other source block restored exactly; helper reads original array, no shadow routing table in runtime.']}, indent=2) + '\n')

base = Path('experiments/wii-static-recomp/verify_stock_scheduler_o2.py')
script = base.read_text()
start = script.index("assert Path(build['sourcePath'])")
end = script.index('temporary = Path(tempfile.mkdtemp', start)
script = script[:start] + script[end:]
patches = [
    ("output = root / 'window-scheduler-o2'", "output = root / 'window-dispatch-o2'"),
    ("parent_path = root / 'window-movie-late/build.json'", "parent_path = root / 'window-scheduler-o2/build.json'"),
    ("flags = parent['changes']['37']['arguments']", "flags = json.loads((root / 'window-movie-late/build.json').read_text())['changes']['37']['arguments']"),
    ("assert prior['buildSha256'] == sha(parent_path)", "assert prior['buildSha256'] == sha(root / 'window-movie-late/build.json')"),
    ("command[command.index(str(old_archive))] = str(archive)", '''old_master = next(arg for arg in command if Path(arg).name == 'fixed.cpp.o')
command[command.index(old_master)] = build['masterObjectPath']
command.insert(1, build['helperObjectPath'])
old_archive = next(arg for arg in command if Path(arg).name == 'libnwiiruntime.a')
new_archive = next(arg for arg in build['linkCommand'] if Path(arg).name == 'libnwiiruntime.a')
command[command.index(old_archive)] = new_archive'''),
    ("SCHEDULER_O2_CONTRACT_CALLBACK4_SDK7_SC3_LATE18_EQUAL", "DISPATCH_O2_ROUTES_CALLBACK4_SDK7_SC3_LATE18_EQUAL")]
for before, after in patches:
    assert before in script
    script = script.replace(before, after)
exec(compile(script, str(base), 'exec'), {'__file__': __file__})
report_path = output / 'component-verification.json'
report = json.loads(report_path.read_text())
report.update(routeProofSha256=sha(output / 'route-verification.json'), baseVerifierSha256=sha(base))
report['limits'] = ['Only exact index lookup extracted into pure O2 helper; original pointer array/master pragmas/setjmp/other bodies retained.',
    'Route partition representatives and synthetic duplicate/empty/extreme inputs equal, callbacks4/SDK7/emittedSC3/18lateframes exact.',
    'Scheduler contracts rechecked against current parent; no new scheduler logic or archive optimization this build.',
    'Native adapters/isolated fixtures, not original Wii runtime/whole-game/controller/visual/audio proof; live acceptance/promotion pending.']
report_path.write_text(json.dumps(report, indent=2) + '\n')
print('DISPATCH_O2_ROUTES_CALLBACK4_SDK7_SC3_LATE18_EQUAL')

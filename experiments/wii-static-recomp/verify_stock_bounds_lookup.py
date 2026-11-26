"""Verify all uint32 routing partitions against the unchanged ordered linear table."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-bounds-lookup'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
original = Path(build['masterOriginalPath'])
assert sha(original) == build['masterOriginalSha256']
master = (output / 'fixed.cpp').read_text()
before, after = build['masterPatch']
assert master.count(after) == 1 and master.count(build['declaration']) == 1
assert master.replace(after, before, 1).replace(build['declaration'], '', 1) == original.read_text()
assert '#pragma clang optimize off' in master and '#pragma GCC optimize ("O0")' in master
for name, key in [('fixed.cpp', 'masterSourceSha256'), ('fixed.cpp.o', 'masterObjectSha256'),
    ('bounds.cpp', 'lookupSourceSha256'), ('bounds.cpp.o', 'lookupObjectSha256'),
    ('OpenSHSMStockBoundsLookup', 'executableSha256')]:
    assert sha(output / name) == build[key]
table = original.read_text().split('static const FuncBound g_func_bounds[] = {', 1)[1].split('};', 1)[0]
records = []
for line in table.splitlines():
    if not line.strip():
        continue
    match = re.fullmatch(r'\s*\{(0x[0-9A-Fa-f]+|0), (0x[0-9A-Fa-f]+|0), (func_[0-9A-Fa-f]+|nullptr)\},?\s*', line)
    assert match
    start, end = int(match[1], 0), int(match[2], 0)
    if start == 0:
        break
    records.append([start, end, match[3]])
assert records == build['records']
points = sorted({0, 0x100000000, *[value for row in records for value in row[:2]],
    *[value for row in build['ranges'] for value in row[:2]]})
queries = sorted({value for start, end in zip(points, points[1:]) for value in (start, end - 1)})
temporary = Path(tempfile.mkdtemp(prefix='openshsm-bounds-proof-', dir='/private/tmp'))
fixture = temporary / 'routing.cpp'
fixture.write_text('''#include "stock_bounds_lookup.h"
#include <cstdio>
extern "C" uint32_t stock_lookup_bounds(uint32_t);
struct Original { uint32_t start; uint32_t end; };
static const Original original[] = {
''' + ''.join(f'    {{0x{start:08X}, 0x{end:08X}}},\n' for start, end, _ in records) +
    '    {0, 0}\n};\nstatic const uint32_t queries[] = {\n' +
    ''.join(f'    0x{query:08X},\n' for query in queries) + '''};
static uint32_t linear(uint32_t target) {
    for (uint32_t index = 0; original[index].start != 0; ++index) {
        if (target >= original[index].start && target < original[index].end) {
            return index;
        }
    }
    return UINT32_MAX;
}
int main() {
    for (uint32_t query : queries) {
        if (stock_lookup_bounds(query) != linear(query)) {
            std::printf("MISMATCH %08x\\n", query);
            return 1;
        }
    }
    uint32_t seed = 0x51534D48;
    for (unsigned i = 0; i < 4096; ++i) {
        seed = seed * 1664525u + 1013904223u;
        if (stock_lookup_bounds(seed) != linear(seed)) {
            return 2;
        }
    }
    const StockBoundsRange empty[] = {{8, 12, 5}};
    if (stock_bounds_index(nullptr, 0, 0) != UINT32_MAX ||
        stock_bounds_index(empty, 1, 7) != UINT32_MAX ||
        stock_bounds_index(empty, 1, 8) != 5 ||
        stock_bounds_index(empty, 1, 11) != 5 ||
        stock_bounds_index(empty, 1, 12) != UINT32_MAX ||
        stock_bounds_index(empty, 1, UINT32_MAX) != UINT32_MAX) {
        return 3;
    }
    std::printf("ALL_UINT32_PARTITIONS_ROUTING_EQUAL %zu\\n", sizeof(queries) / sizeof(queries[0]));
    return 0;
}
''')
exe = temporary / 'routing'
command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-isysroot', build['sdk'], '-std=c++20', '-O2',
    '-I', str(output), str(fixture), str(output / 'bounds.cpp.o'), '-o', str(exe)]
compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
assert compiled.returncode == 0, compiled.stderr
run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
assert run.returncode == 0, run.stdout + run.stderr
(output / 'routing-verification.json').write_text(json.dumps({
    'result': 'ALL_UINT32_PARTITIONS_ROUTING_EQUAL', 'buildSha256': sha(build_path),
    'originalRecords': len(records), 'disjointRanges': len(build['ranges']),
    'partitionCount': len(points) - 1, 'boundaryQueries': len(queries), 'randomQueries': 4096,
    'fixturePath': str(fixture), 'fixtureSha256': sha(fixture),
    'executablePath': str(exe), 'executableSha256': sha(exe),
    'verifierSha256': sha(Path(__file__)), 'terminalReturncode': run.returncode,
    'stdout': run.stdout,
    'limits': ['Both predicates constant within every partition of original and derived endpoints; boundary checks cover full uint32 domain.',
        'Compares original record identity, not just function identity; ordered overlaps preserve first-match behavior.',
        'Same source/output restoration and retained input hashes checked; not guest execution or Wii hardware oracle.',
        'No live speed/FPS/audio/visual/profile/save/controller claim; full frame and counter-free GUI checks pending.']}, indent=2) + '\n')
print(run.stdout.strip(), len(records), len(build['ranges']))

proof = json.loads((root / 'window-decoder-o3/verification.json').read_text())
fixture_obj = root / 'window-decoder-o3/frame-probe.cpp.o'
assert sha(fixture_obj) == proof['fixtureObjectSha256']
frame_exe = temporary / 'frame-probe'
command = list(build['linkCommand'])
main = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
command[command.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
command.insert(1, str(fixture_obj))
command[command.index('-o') + 1] = str(frame_exe)
linked = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert linked.returncode == 0, linked.stderr[-2500:]
snapshot = root / 'headless-sc-pc-decoder-snapshot-retry-decoder-entry.bin'
packet = root / 'headless-thp-snapshot/hm1ply-frame15-replay/hm1ply-frame15.packet'
assert sha(snapshot) == proof['snapshotSha256'] and sha(packet) == proof['packetSha256']
reference = root / 'window-decoder-o3/baseline-0.yuv'
state = Path(str(reference) + '.state')
frames = []
for iteration in range(3):
    raw = output / f'probe-{iteration}.yuv'
    timing = output / f'probe-{iteration}-timing.jsonl'
    assert not timing.exists()
    env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
    env['NWII_MOVIE_TIMING'] = str(timing)
    replay = subprocess.run([str(frame_exe), str(snapshot), str(raw), str(packet)], env=env,
        capture_output=True, text=True, timeout=30)
    log = output / f'probe-{iteration}.log'
    log.write_text(replay.stdout + replay.stderr)
    assert replay.returncode == 0, replay.stderr[-2000:]
    assert raw.read_bytes() == reference.read_bytes()
    assert Path(str(raw) + '.state').read_bytes() == state.read_bytes()
    events = [json.loads(line) for line in timing.read_text().splitlines()]
    assert [row['site'] for row in events] == [0x80209D80, 0x8020A044]
    frames.append({'outputSha256': sha(raw), 'stateSha256': sha(Path(str(raw) + '.state')),
        'logSha256': sha(log), 'timingSha256': sha(timing),
        'wallUs': events[1]['hostUs'] - events[0]['hostUs']})
(output / 'component-verification.json').write_text(json.dumps({
    'result': 'BOUNDS_LOOKUP_FRAME_STATE_IDENTICAL3', 'buildSha256': sha(build_path),
    'routingProofSha256': sha(output / 'routing-verification.json'),
    'verifierSha256': sha(Path(__file__)), 'executablePath': str(frame_exe),
    'executableSha256': sha(frame_exe), 'frames': frames,
    'limits': ['Same owned complete frame exact YUV and selected final PPC state/instruction count.',
        'Direct decoder fixture does not exercise run_game routing; exhaustive routing proof is separate.',
        'Counter-free live master execution/IRQ/visual/audio/FPS acceptance pending.']}, indent=2) + '\n')
print('BOUNDS_LOOKUP_FRAME_STATE_IDENTICAL3', frames)

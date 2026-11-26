"""Compare compiled owner bounds lookup with every partition of its actual function table."""
from pathlib import Path
import argparse
import json
import re
import shutil
import subprocess

from export_stock_wii_us_copy import digest


def verify(source, output, compiler):
    source = source.resolve(strict=True)
    output = output.absolute()
    output = output.parent.resolve(strict=True) / output.name
    if output.exists() or output.is_symlink():
        raise ValueError('Verification output must be fresh')
    fixed = (source / 'fixed.cpp').read_text()
    table = fixed.split('static const FuncBound g_func_bounds[] = {', 1)[1].split('};', 1)[0]
    original = [(int(start, 16), int(end, 16), name) for start, end, name in re.findall(
        r'\{0x([0-9A-Fa-f]+), 0x([0-9A-Fa-f]+), (func_[0-9A-Fa-f]+)\}', table)]
    derived = [(int(start, 16), int(end, 16), int(index)) for start, end, index in re.findall(
        r'\{0x([0-9A-Fa-f]+), 0x([0-9A-Fa-f]+), ([0-9]+)\}',
        (source / 'bounds.cpp').read_text())]
    if not original or not derived or any(start >= end for start, end, _ in original + derived):
        raise ValueError('Invalid or empty owner bounds table')
    points = sorted({0, 0x100000000,
        *[value for start, end, _ in original + derived for value in (start, end)]})
    queries = sorted({value for start, end in zip(points, points[1:]) for value in (start, end - 1)})
    output.mkdir(mode=0o700)
    fixture = output / 'routing.cpp'
    fixture.write_text('''#include <cstdint>
#include <cstdio>
extern "C" uint32_t stock_lookup_bounds(uint32_t);
struct Range { uint32_t start, end; };
static const Range original[] = {
''' + ''.join(f'    {{0x{start:08X}, 0x{end:08X}}},\n' for start, end, _ in original) +
        '};\nstatic const uint32_t queries[] = {\n' +
        ''.join(f'    0x{query:08X},\n' for query in queries) + '''};
static uint32_t linear(uint32_t pc) {
    for (uint32_t i = 0; i < sizeof(original) / sizeof(original[0]); ++i) {
        if (pc >= original[i].start && pc < original[i].end) {
            return i;
        }
    }
    return UINT32_MAX;
}
static bool check(uint32_t pc) {
    const uint32_t actual = stock_lookup_bounds(pc), expected = linear(pc);
    if (actual != expected) {
        std::printf("BOUNDS_MISMATCH pc=%08x actual=%u expected=%u\\n", pc, actual, expected);
        return false;
    }
    return true;
}
int main() {
    if (!check(0x802DA128)) {
        return 1;
    }
    for (uint32_t pc : queries) {
        if (!check(pc)) {
            return 1;
        }
    }
    uint32_t seed = 0x51534D48;
    for (unsigned i = 0; i < 4096; ++i) {
        seed = seed * 1664525u + 1013904223u;
        if (!check(seed)) {
            return 1;
        }
    }
    std::printf("OWNER_BOUNDS_ALL_UINT32_PARTITIONS_PASS %zu\\n", sizeof(queries) / sizeof(queries[0]));
}
''')
    executable = output / 'routing'
    command = [str(compiler), '-std=c++20', '-O2', '-I', str(Path(__file__).resolve().parent),
        str(fixture), str(source / 'bounds.cpp'), '-o', str(executable)]
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=180)
    (output / 'compile.log').write_text(compiled.stdout + compiled.stderr)
    if compiled.returncode:
        raise RuntimeError(compiled.stderr[-2000:])
    ran = subprocess.run([str(executable)], capture_output=True, text=True, timeout=60)
    report = {'result': 'OWNER_BOUNDS_ALL_UINT32_PARTITIONS_PASS' if ran.returncode == 0 else
        'OWNER_BOUNDS_ROUTING_MISMATCH', 'source': str(source),
        'functionRecords': len(original), 'derivedRanges': len(derived),
        'partitions': len(points) - 1, 'boundaryQueries': len(queries), 'randomQueries': 4096,
        'criticalResume': {'pc': '0x802DA128', 'expectedIndex': next(
            i for i, (start, end, _) in enumerate(original) if start <= 0x802DA128 < end)},
        'fixedSha256': digest(source / 'fixed.cpp'), 'boundsSha256': digest(source / 'bounds.cpp'),
        'executableSha256': digest(executable), 'verifierSha256': digest(Path(__file__)),
        'compileCommand': command, 'returncode': ran.returncode, 'stdout': ran.stdout,
        'limits': ['Compiled lookup compared with the actual ordered linear function table.',
            'Endpoint partitions cover the uint32 routing domain; original first-match order is preserved.',
            'Routing contract only; visual, audio, controller and full-game acceptance are separate.']}
    (output / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return ran.returncode


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-tree', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compiler', type=Path, default=shutil.which('c++'))
    args = parser.parse_args()
    if args.compiler is None:
        parser.error('Supply a C++20 compiler with --compiler')
    raise SystemExit(verify(args.source_tree, args.output, args.compiler))

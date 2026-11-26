"""Pin and execute Dolphin's unmodified numerical estimate oracle, not game code."""
from pathlib import Path
import argparse
import hashlib
import json
import random
import subprocess
import tempfile


REVISION = 'e2ad09306e6d371f7272205bdc363da9fe05fe08'
BASE_URL = f'https://raw.githubusercontent.com/dolphin-emu/dolphin/{REVISION}/'
FILES = (
    'Source/Core/Common/FloatUtils.cpp',
    'Source/Core/Common/FloatUtils.h',
    'Source/Core/Core/PowerPC/Interpreter/Interpreter_Paired.cpp',
    'Source/Core/Core/PowerPC/Interpreter/Interpreter_FPUtils.h',
    'Source/Core/Core/PowerPC/PowerPC.h',
    'Source/Core/Core/PowerPC/PowerPC.cpp',
    'Source/Core/Core/PowerPC/Gekko.h',
    'COPYING',
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    public = Path(__file__).resolve().parent
    if args.output:
        cache = args.output.resolve()
        cache.mkdir(parents=True, exist_ok=False)
    else:
        scratch = public.parents[1] / '_scratch/tmp'
        scratch.mkdir(parents=True, exist_ok=True)
        cache = Path(tempfile.mkdtemp(prefix='openshsm-paired-reference-', dir=scratch))
    references = []
    for name in FILES:
        destination = cache / 'dolphin' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['curl', '--fail', '--silent', '--show-error', '--location',
            '--max-time', '30', BASE_URL + name, '-o', str(destination)], check=True, timeout=40)
        references.append({'url': BASE_URL + name, 'path': str(destination), 'sha256': sha(destination)})
    common = cache / 'dolphin/Source/Core/Common'
    for name in ('FloatUtils.cpp', 'FloatUtils.h'):
        assert 'SPDX-License-Identifier: GPL-2.0-or-later' in (common / name).read_text()
    shim = cache / 'shim/Common/CommonTypes.h'
    shim.parent.mkdir(parents=True)
    shim.write_text('#pragma once\n#include <cstdint>\nusing u32 = uint32_t;\n'
        'using u64 = uint64_t;\nusing s64 = int64_t;\n')
    source = public / 'stock_paired_estimate_reference.cpp'
    exe = cache / 'reference'
    command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++20', '-O2',
        '-fno-fast-math', '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
        '-isysroot', '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk',
        '-I', str(cache / 'shim'), '-I', str(cache / 'dolphin/Source/Core'),
        str(source), str(common / 'FloatUtils.cpp'), '-o', str(exe)]
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (cache / 'compile.log').write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0, compiled.stderr
    samples = {0, 1, 0x000fffffffffffff, 0x0010000000000000,
        0x3ff0000000000000, 0x4000000000000000, 0x4010000000000000,
        0x7fefffffffffffff, 0x7ff0000000000000, 0x7ff0000000000001,
        0x7ff8000000000001, 0x7fffffffffffffff}
    for exponent in (894, 895, 896, 1022, 1023, 1024, 1148, 1149):
        for index in range(32768):
            samples.add((exponent << 52) | (index << 37))
    generator = random.Random(0x5348534d)
    samples.update(generator.getrandbits(63) for _ in range(20000))
    samples.update(value | (1 << 63) for value in tuple(samples))
    ordered = sorted(samples)
    inputs = cache / 'input-bits.txt'
    inputs.write_text(''.join(f'{value:016x}\n' for value in ordered))
    fixture = cache / 'estimate-bits.txt'
    with inputs.open() as stdin, fixture.open('w') as stdout:
        run = subprocess.run([str(exe)], stdin=stdin, stdout=stdout,
            stderr=subprocess.PIPE, text=True, timeout=40)
    (cache / 'run.log').write_text(run.stderr)
    assert run.returncode == 0, run.stderr
    count, reciprocal_mismatches, square_root_mismatches = map(int, run.stderr.split())
    assert count == len(ordered)
    rows = {}
    with fixture.open() as stream:
        for index, line in enumerate(stream):
            bits, reciprocal, square_root = (int(field, 16) for field in line.split())
            assert bits == ordered[index]
            rows[bits] = (reciprocal, square_root)
    assert len(rows) == count
    assert rows[0] == (0x7ff0000000000000, 0x7ff0000000000000)
    assert rows[1 << 63] == (0xfff0000000000000, 0xfff0000000000000)
    assert rows[0x7ff0000000000000] == (0, 0)
    assert rows[0xfff0000000000000][0] == 1 << 63
    for bits in (0x7ff0000000000001, 0x7ff8000000000001, 0x7fffffffffffffff):
        for signed in (bits, bits | (1 << 63)):
            assert rows[signed] == (signed | 0x0008000000000000,) * 2
    assert rows[1][0] == 0x47efffffe0000000
    dependencies = {str(path): sha(path) for path in
        (Path(__file__).resolve(), source, shim, inputs, fixture, exe)}
    report = {'result': 'PINNED_DOLPHIN_NUMERIC_ESTIMATE_REFERENCE_EXECUTED',
        'revision': REVISION, 'references': references, 'dependencies': dependencies,
        'command': command, 'samples': count,
        'hostExactReciprocalBitMismatches': reciprocal_mismatches,
        'hostExactReciprocalSquareRootBitMismatches': square_root_mismatches,
        'limits': ['Unmodified Dolphin numerical functions, not original Wii hardware execution.',
            'CommonTypes shim supplies integer aliases only; no replacement estimate algorithm.',
            'No ForceSingle, paired lane, FPSCR, CR1, NI or exception-routing verification yet.',
            'No game runtime instruction implementation, live launch or crash fix in this report.',
            'GPL-2.0-or-later reference/license retained privately; no source or asset publication.']}
    path = cache / 'reference.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, count, reciprocal_mismatches, square_root_mismatches, flush=True)


if __name__ == '__main__':
    main()

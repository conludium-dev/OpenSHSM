"""Independent pinned conversion-body comparisons and actual indexed RAM contracts."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import tempfile
from verify_stock_paired_estimates import function


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--baseline-header', type=Path, required=True)
    args = parser.parse_args()
    reference = json.loads(args.reference.read_text())
    assert reference['revision'] == 'e2ad09306e6d371f7272205bdc363da9fe05fe08'
    row = next(row for row in reference['references'] if row['path'].endswith('/Interpreter_FPUtils.h'))
    fp = Path(row['path'])
    assert sha(fp) == row['sha256']
    public = Path(__file__).resolve().parent
    root = public.parents[1] / 'work/private-game/static-recomp/stock-baseline'
    cache = Path(tempfile.mkdtemp(prefix='openshsm-psq-float-', dir='/private/tmp'))
    header = cache / 'psq-float-reference.h'
    text = fp.read_text()
    header.write_text('// Copyright 2008 Dolphin Emulator Project\n'
        '// SPDX-License-Identifier: GPL-2.0-or-later\n#include <cstdint>\n'
        'using u32 = uint32_t; using u64 = uint64_t;\n'
        'namespace Common { constexpr u64 DOUBLE_SIGN = 0x8000000000000000ull; }\n' +
        function(text, 'inline u32 ConvertToSingleFTZ(') + function(text, 'inline u64 ConvertToDouble('))
    source = public / 'stock_psq_float_contract.cpp'
    runs = {}
    for name, tested, definitions, expected in (
            ('baseline', args.baseline_header.resolve(), ['-DSHSM_PSQ_BASELINE'],
                'BASELINE_NONREPRESENTABLE_PSQ_STORE_REFUSAL_REPRODUCED'),
            ('candidate', public / 'stock_psq_indexed.h', [], 'PSQ_FLOAT_BITS_COMPONENT_PASS'),
            ('legacy-contract', public / 'stock_psq_indexed.h', [], 'PASS 8192')):
        exe = cache / name
        tested_source = public / 'stock_psq_contract.cpp' if name == 'legacy-contract' else source
        command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++20', '-O2',
            '-fno-fast-math', '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
            '-isysroot', '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk',
            '-I', str(root / 'window-quantization/include'), '-I', str(public), '-I', str(cache),
            f'-DSHSM_PSQ_HEADER="{tested}"', *definitions, str(tested_source), '-o', str(exe)]
        compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
        (cache / (name + '-compile.log')).write_text(compiled.stdout + compiled.stderr)
        assert compiled.returncode == 0, compiled.stderr
        run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
        (cache / (name + '-run.log')).write_text(run.stdout + run.stderr)
        assert run.returncode == 0 and expected in run.stdout, (name, run.returncode, run.stdout, run.stderr)
        runs[name] = {'command': command, 'executablePath': str(exe), 'executableSha256': sha(exe),
            'output': run.stdout.strip(), 'headerSha256': sha(tested)}
    report = {'result': 'INDEXED_PSQ_FLOAT_CONVERSION_COMPONENT_PASS', 'runs': runs,
        'referenceRevision': reference['revision'],
        'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), source,
            public / 'stock_psq_indexed.h', public / 'stock_psq_float.h', args.reference, args.baseline_header,
            public / 'stock_psq_contract.cpp',
            fp, header, public / 'stock_quantization_contract.cpp',
            root / 'window-quantization/include/runtime/cpu_context.h']},
        'limits': ['Pinned Dolphin conversion bodies, not Wii hardware or live operand capture.',
            'RAM/GQR type0 indexed operations only; other quantization/MMIO/DSI profiles still refused.',
            'No affected game units rebuilt/linked, live transition or save acceptance yet.',
            'All callers must be rebuilt together to avoid inline ODR mixing with old guard.']}
    path = cache / 'verification.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, runs['candidate']['output'], flush=True)


if __name__ == '__main__':
    main()

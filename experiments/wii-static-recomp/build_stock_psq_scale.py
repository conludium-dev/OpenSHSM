"""Derive equivalent finite pow2 scaling helpers; retain all dynamic GQR/MMU/FP checks."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'headless-psq-scale'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base_path = root / 'headless-constant-fp/build.json'
base = json.loads(base_path.read_text())
for path, expected in {**base['dependencies'], **base['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
header = root / 'window-quantization/include/runtime/cpu_context.h'
cpu = header.read_text()
start = cpu.index('  void psq_load(')
end = cpu.index('  inline void ps_add(', start)
body = cpu[start:end]
assert body.count('std::ldexp(1.0f, -signed_scale)') == 1
assert body.count('std::ldexp(1.0f, signed_scale)') == 1
body = body.replace('  void psq_load(', '  inline void stock_psq_load(CPUContext& ctx, ')
body = body.replace('  void psq_store(', '  inline void stock_psq_store(CPUContext& ctx, ')
for member in ('gqr', 'mmu', 'fpr', 'ps1'):
    body = re.sub(rf'\b{member}\b', 'ctx.' + member, body)
body = body.replace('std::ldexp(1.0f, -signed_scale)', 'std::bit_cast<float>(uint32_t(127 - signed_scale) << 23)')
body = body.replace('std::ldexp(1.0f, signed_scale)', 'std::bit_cast<float>(uint32_t(127 + signed_scale) << 23)')
helper = output / 'psq_scale.h'
helper.write_text('#pragma once\n#include "runtime/cpu_context.h"\n#include <bit>\nnamespace nwii::runtime {\n' + body + '\n}\n')
command = list(base['linkCommand'])
old = next(Path(arg) for arg in command if Path(arg).name == 'output_37.cpp.o')
original = old.with_suffix('')
assert sha(original) == base['sourceSha256']
text = original.read_text()
counts = {name: text.count(f'ctx.{name}(') for name in ('psq_load', 'psq_store')}
assert all(counts.values())
for name in counts:
    text = text.replace(f'ctx.{name}(', f'stock_{name}(ctx, ')
source, obj = output / original.name, output / old.name
source.write_text('#include "psq_scale.h"\n' + text)
record = json.loads((root / 'window-fp-guard/output_37.cpp.record.json').read_text())
assert sha(header) == record['dependencies'][str(header)]
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'], '-I', str(original.parent),
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
command[command.index(str(old))] = str(obj)
exe = output / 'OpenSHSMStockPSQScale'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=180)
(output / 'build.json').write_text(json.dumps({'result': 'PSQ_POW2_BUILT_DIFFERENTIAL_PERFORMANCE_UNVERIFIED',
    'baseBuildSha256': sha(base_path), 'sourceSha256': sha(source), 'objectSha256': sha(obj),
    'executableSha256': sha(exe), 'archiveSha256': base['archiveSha256'], 'linkCommand': command, 'counts': counts,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), header, helper]},
    'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).suffix == '.o'},
    'limits': ['Generated private helper derives unchanged MMU/GQR/type/NaN/clamp logic from existing header.',
        'Only pow2 construction changed: signed6bit scale yields finite normal IEEEfloat exponents95..159.',
        'Only decoder unit37 replaced; no CPUContext ABI/header/runtime/other74guest change or guard bypass.',
        'Differential/end-to-end output/timing proof required; not original Wii hardware equivalence.']}, indent=2) + '\n')
print('PSQ_POW2_BUILT_DIFFERENTIAL_PERFORMANCE_UNVERIFIED', counts)

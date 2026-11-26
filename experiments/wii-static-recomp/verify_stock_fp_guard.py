"""Compare CPU classification with independently parsed Dolphin opcode metadata."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base = root / 'window-quantization'
output = root / 'fp-guard-component'
output.mkdir(exist_ok=True)
reference = Path('_scratch/tmp/stock-fp-PPCTables.cpp').resolve()
text = reference.read_text()
tables = {}
for name in ('primary_table', 'table4', 'table4_2', 'table4_3', 'table31', 'table59', 'table63', 'table63_2'):
    body = re.search(r's_' + name + r'\{\{(.*?)\}\};', text, re.S).group(1)
    rows = re.findall(r'\{(\d+), "([^"]+)",(.*?)\}', body, re.S)
    tables[name] = {int(code) for code, label, flags in rows if 'FL_USE_FPU' in flags}
assert len(tables['table31']) == 9 and len(tables['table63']) == 15
expected = []
for primary in range(64):
    for xo in range(1024):
        uses = primary in tables['primary_table']
        if primary == 4:
            uses = xo in tables['table4'] or (xo & 31) in tables['table4_2'] or (xo & 63) in tables['table4_3']
        elif primary == 31:
            uses = xo in tables['table31']
        elif primary == 59:
            uses = (xo & 31) in tables['table59']
        elif primary == 63:
            uses = xo in tables['table63'] or (xo & 31) in tables['table63_2']
        expected.append(int(uses))
header = output / 'fp-classification.h'
header.write_text('const unsigned char fp_expected[] = {' + ','.join(map(str, expected)) + '};\n')
source = Path('experiments/wii-static-recomp/stock_fp_guard_contract.cpp').resolve()
exe = output / 'fp-guard-contract'
command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++20', '-O2',
    '-isysroot', '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk',
    '-I', str(base / 'include'), '-I', str(base), '-I', str(output), str(source), '-o', str(exe)]
result = subprocess.run(command, capture_output=True, text=True, timeout=60)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=20)
(output / 'run.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stdout + result.stderr
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
inputs = [reference, header, source, exe, Path(__file__).resolve(),
    Path('experiments/wii-static-recomp/stock_fp_unavailable.h'), base / 'processor_adapter.h',
    Path('experiments/wii-static-recomp/stock_quantization_contract.cpp'), base / 'include/runtime/cpu_context.h']
(output / 'report.json').write_text(json.dumps({'result': 'FP_CLASSIFICATION_NONLOCAL_COMPONENT_PASS',
    'output': result.stdout.strip(), 'tables': {name: sorted(values) for name, values in tables.items()},
    'inputs': [{'path': str(path.resolve()), 'sha256': sha(path)} for path in inputs], 'command': command,
    'referenceUrl': 'https://raw.githubusercontent.com/dolphin-emu/dolphin/master/Source/Core/Core/PowerPC/PPCTables.cpp',
    'limits': ['Opcode metadata oracle, not original Wii dynamic execution.',
        'Paired illegal-execution profiles throw before FP trap; program exception delivery still unverified.',
        'CPU guard/nonlocal transfer only; existing arithmetic/FPSCR inaccuracies not validated by this test.']}, indent=2) + '\n')
print(result.stdout.strip())

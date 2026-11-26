"""Verify atomic rejection of unsupported profiles and sanitizer execution of both matrices."""
from pathlib import Path
import json
import hashlib
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-general-subtract')
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
source = output / 'general-subtract-contract.cpp'
body = (experiment / 'single_arithmetic_contract.cpp').read_text().replace('single_arithmetic_adapter.h', 'general_subtract_adapter.h').replace(
    'experiment_single_arithmetic', 'experiment_general_subtract').replace('0xec220824', '0xec020028').replace(
    '        refuse(0xec000072);\n', '').replace('SINGLE_ARITHMETIC_CONTRACT', 'GENERAL_SUBTRACT_CONTRACT').replace(
    '{0xec220825u, 0xec000073u, 0xfc220824u, 0xec220828u}', '{0xec020029u, 0xfc020028u, 0xec020068u, 0xec02002au}')
source.write_text(body)
includes = ['-I', str(experiment), '-I', 'work/private-game/static-recomp/mass-ni-guard', '-I', str(runtime / 'include')]
lines = []
for directory in (output, output.with_name('dolphin-general-subtract-targeted')):
    generation = json.loads((directory / 'generation.json').read_text())
    lines.extend(f"{row['a']} {row['b']} {row['initialFpscr'] | row['ni'] * 4} {row['opcode']}\n" for row in generation['records'])
for cpp, name in ((source, 'general-subtract-contract'), (experiment / 'general_subtract_probe.cpp', 'general-subtract-ubsan')):
    exe = output / name
    result = subprocess.run(['clang++', '-std=c++20', '-O1', '-fsanitize=undefined', '-fno-sanitize-recover=all',
        *includes, str(cpp), '-o', str(exe)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    result = subprocess.run([str(exe)], input=''.join(lines) if name.endswith('ubsan') else '',
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0 and not result.stderr, result.stderr
    if name.endswith('ubsan'):
        assert len(result.stdout.splitlines()) == len(lines) == 5120
    else:
        assert result.stdout == 'GENERAL_SUBTRACT_CONTRACT guards=12\n'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'contract-verification.json').write_text(json.dumps({'result': 'PASS_SUBTRACT12_REFUSALS_UBSAN5120',
    'verifierSha256': sha(Path(__file__)), 'adapterSha256': sha(experiment / 'general_subtract_adapter.h'),
    'contractSha256': sha(source), 'limits': ['MacARM64clang only; not full FPU or physical Wii proof.']}, indent=2) + '\n')
print('PASS subtraction12 atomic refusals/UBSan5120 original inputs')

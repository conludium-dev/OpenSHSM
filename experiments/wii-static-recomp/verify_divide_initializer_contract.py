"""Check aliasing division refusal contracts against the exact prepared dispatch."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
component = Path('work/private-game/static-recomp/divide-initializer-component')
output = Path('work/private-game/static-recomp/mass-divide-initializer-boot')
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'prepare_divide_initializer_component.py')], check=True)
assert (output / 'divide_initializer_adapter.h').read_bytes() == (component / 'divide_initializer_adapter.h').read_bytes()
assert (output / 'divide_initializer_probe.h').read_bytes() == (component / 'divide_initializer_probe.h').read_bytes()
source = component / 'divide-contract.cpp'
body = (experiment / 'single_arithmetic_contract.cpp').read_text().replace('single_arithmetic_adapter.h', 'divide_initializer_adapter.h').replace(
    'experiment_single_arithmetic', 'experiment_divide_initializer').replace('0xec220824', '0xec010024').replace(
    '        refuse(0xec000072);\n', '').replace('SINGLE_ARITHMETIC_CONTRACT', 'DIVIDE_INITIALIZER_CONTRACT').replace(
    '{0xec220825u, 0xec000073u, 0xfc220824u, 0xec220828u}', '{0xec010025u, 0xfc010024u, 0xec010064u, 0xec010028u}')
source.write_text(body)
exe = component / 'divide-contract'
result = subprocess.run(['clang++', '-std=c++20', '-O1', '-fsanitize=undefined', '-fno-sanitize-recover=all',
    '-I', str(component), '-I', str(experiment), '-I', 'work/private-game/static-recomp/mass-ni-guard', '-I', str(runtime / 'include'), str(source), '-o', str(exe)],
    capture_output=True, text=True, timeout=30)
assert result.returncode == 0, result.stderr
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
assert result.returncode == 0 and not result.stderr and result.stdout == 'DIVIDE_INITIALIZER_CONTRACT guards=12\n', result
(component / 'contract-verification.json').write_text(json.dumps({'result': 'PASS_DIVIDE_ROUTING12_REFUSALS',
    'verifierSha256': sha(Path(__file__)), 'headerSha256': sha(component / 'divide_initializer_adapter.h'),
    'contractSha256': sha(source), 'executableSha256': sha(exe),
    'limits': ['Refusal path sanitizer only; whole-function equivalence checked separately; MacARM64clang only.']}, indent=2) + '\n')
print('PASS divide-routing12 atomic refusals/sanitized refusal path/exact dispatch regeneration')

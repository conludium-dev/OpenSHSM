"""Compare specialized guards to retained runtime guards, including nonlocal exceptions/refusals."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'headless-constant-fp'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
base = json.loads(build_path.read_text())
for path, expected in {**base['dependencies'], **base['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
opcodes = sorted(set(item['opcode'] for item in base['sites']))
cases = '#pragma once\n#include "constant_fp_guard.h"\n#include <array>\nusing namespace nwii::runtime;\n'
cases += 'struct GuardCase { uint32_t opcode; bool uses_fp; void (*call)(CPUContext&, uint32_t); };\n'
cases += f'inline const std::array<GuardCase, {len(opcodes)}> cases = {{{{\n'
cases += ''.join(f'{{0x{opcode:08X}, stock_constant_uses_fp(0x{opcode:08X}), &stock_constant_fp_preinstruction<0x{opcode:08X}>}},\n' for opcode in opcodes)
cases += '}};\n'
(output / 'constant_fp_cases.h').write_text(cases)
record = json.loads((root / 'window-fp-guard/output_37.cpp.record.json').read_text())
for path, expected in record['dependencies'].items():
    assert sha(Path(path)) == expected, path
parent_path = root / 'headless-movie-timing/build.json'
parent = json.loads(parent_path.read_text())
assert sha(parent_path) == base['baseBuildSha256']
assert parent['changes']['37']['sourceSha256'] == base['originalSourceSha256']
assert sha(root / 'headless-movie-timing/output_37.cpp') == base['originalSourceSha256']
source, obj = public / 'stock_constant_fp_probe.cpp', output / 'probe.cpp.o'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'], '-I', str(output),
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'probe-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2000:]
command = list(base['linkCommand'])
command[command.index(str(root / 'headless-tev-banks/main.cpp.o'))] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
command.insert(1, str(obj))
exe = output / 'guard-probe'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
(output / 'probe.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
assert f'CONSTANT_FP_DIFFERENTIAL_PASS {len(opcodes) * 40}' in result.stdout
(output / 'guard-verification.json').write_text(json.dumps({'result': 'CONSTANT_FP_DIFFERENTIAL_PASS',
    'cases': len(opcodes) * 40, 'uniqueOpcodes': len(opcodes), 'buildSha256': sha(build_path),
    'probeSourceSha256': sha(source), 'casesHeaderSha256': sha(output / 'constant_fp_cases.h'),
    'executableSha256': sha(exe), 'logSha256': sha(output / 'probe.log'), 'verifierSha256': sha(Path(__file__).resolve()),
    'retainedGuardDependencies': record['dependencies'],
    'limits': ['All unique unit37 guarded words;10MSR x4HID2 states; actual runtime HID2 accessor.',
        'Native guard differential covers successful gates, trap state and unsupported/privileged refusal order/messages.',
        'Not complete original instruction arithmetic, independent Wii oracle, GUI or movie performance acceptance.']}, indent=2) + '\n')
print(result.stdout.strip())

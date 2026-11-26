"""Check the bounded observation delta and all retained module/data contracts."""
from pathlib import Path
import ast
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
base = root / 'mass-divide-initializer-boot'
output = root / 'mass-constructor-budget-observer'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((base / 'build.json').read_text())
observation = json.loads((output / 'observation.json').read_text())
assert observation['builderSha256'] == sha(experiment / 'observe_constructor_budget.py')
assert observation['baseBuildSha256'] == sha(base / 'build.json')
assert observation['records'] == build['records'] and len(build['records']) == 125
for row in observation['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for path, digest in {**observation['sourceHashes'], **observation['headerHashes']}.items():
    assert sha(Path(path)) == digest
assert observation['executableSha256'] == sha(output / 'es-vector-observer')
for path in base.glob('*.h'):
    assert (output / path.name).read_bytes() == path.read_bytes()
for name in ('boot-wrapper.cpp', 'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'di_device.cpp', 'boot-quarantine.tsv'):
    assert (output / name).read_bytes() == (base / name).read_bytes()
tree = ast.parse((experiment / 'observe_constructor_budget.py').read_text())
observer = ast.literal_eval(next(node.value for node in tree.body if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id == 'observer' for target in node.targets)))
expected = (base / 'mass_boot.cpp').read_text().replace('if (++calls > 20000)', 'if (++calls > 40000)').replace(
    '        std::cout << "BOOT_ES_LAYOUT "', observer + '        std::cout << "BOOT_ES_LAYOUT "')
assert (output / 'mass_boot.cpp').read_text() == expected
log = (output / 'observation.log').read_text()
assert observation['logSha256'] == sha(output / 'observation.log')
assert 'reason=NI unsupported FP before instruction address=8017ad30 opcode=ec201028' in log
assert 'Function-call budget exceeded' not in log
assert 'BOOT_STM submitted=48 produced=23' in log
tree = ast.parse((experiment / 'audit_playrecord_dec_boot.py').read_text())
prefixes = ast.literal_eval(next(node.iter for node in tree.body if isinstance(node, ast.For)
    and isinstance(node.target, ast.Name) and node.target.id == 'prefix'))
prior = (base / 'live-audit.log').read_text()
for prefix in prefixes:
    rows = [line for line in log.splitlines() if line.startswith(prefix)]
    assert rows and rows == [line for line in prior.splitlines() if line.startswith(prefix)], prefix
operands = next(line for line in log.splitlines() if line.startswith('CONSTRUCTOR_BOUNDARY_OPERANDS '))
assert operands.split()[1] == '4330000080000210' and operands.split()[-2] == '4330000080000000'
(output / 'audit.json').write_text(json.dumps({'result': 'PASS_CALL_BUDGET40000_SAME125_PRIOR_DATA',
    'auditSha256': sha(Path(__file__)), 'observationSha256': sha(output / 'observation.json'),
    'limits': ['Diagnostic limit extension only, not original execution timing or original new-opcode proof.']}, indent=2) + '\n')
print('PASS call-budget40000/exact read-only delta/all125 objects/prior buffers; ' + operands)

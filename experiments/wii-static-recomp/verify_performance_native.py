"""Compare six original recompiled setters to retained Dolphin reset observations."""
from pathlib import Path
import hashlib
import json
import subprocess
from performance_lowering import lower

experiment = Path('experiments/wii-static-recomp')
base = Path('work/private-game/static-recomp/mass-timebase')
output = Path('work/private-game/static-recomp/mass-performance')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_performance_dolphin.py')], check=True)
proof_path = Path('work/private-game/static-recomp/dolphin-performance-probe/comparison.json')
proof = json.loads(proof_path.read_text())
generation = json.loads(Path('work/private-game/static-recomp/dolphin-performance-probe/generation.json').read_text())
lowering = json.loads((output / 'lowering.json').read_text())
assert lowering['sites'] == 6 and lowering['baseLoweringSha256'] == sha(base / 'lowering.json')
assert lowering['adapterSha256'] == sha(experiment / 'performance_adapter.h')
assert lowering['probeSha256'] == sha(experiment / 'performance_probe.h')
assert lowering['scriptSha256'] == sha(experiment / 'build_performance.py')
assert lowering['baseBuilderSha256'] == sha(experiment / 'build_branch.py')
assert lowering['lowererSha256'] == sha(experiment / 'performance_lowering.py')
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
prior = {record['file']: record for record in json.loads((base / 'lowering.json').read_text())['records']}
assert len(lowering['records']) == len(prior) == 125
for record in lowering['records']:
    old = prior[record['file']]
    source = Path(record['directory']) / record['file']
    original = Path(old['directory']) / old['file']
    assert sha(original) == old['sourceSha256']
    expected, changes = lower(original.read_text(), dol)
    assert source.read_text() == expected and record['changes'] == changes
    assert sha(source) == record['sourceSha256'] and sha(Path(str(source) + '.o')) == record['objectSha256']
exe = output / 'openshsm-mass-boot'
boot = json.loads((output / 'boot.json').read_text())
assert boot['executableSha256'] == sha(exe)
assert boot['wrapperSha256'] == sha(output / 'boot-wrapper.cpp')
inputs, expected = [], []
for initial, observed in zip(generation['records'], proof['observations']):
    inputs.append([initial['initialPmcSeed'], initial['cr'], initial['xer'], initial['ctr'], *initial['initialGpr']])
    expected.append([*observed['gpr'], observed['cr'], observed['lr'], observed['ctr'], observed['xer'], observed['msr'], *observed['registers']])
result = subprocess.run([str(exe), '--performance-check'], input=''.join(' '.join(map(str, row)) + '\n' for row in inputs),
                        capture_output=True, text=True, timeout=30)
(output / 'native-comparison.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, (result.returncode, result.stderr)
assert [list(map(int, line.split())) for line in result.stdout.splitlines()] == expected
report = {'result': 'ORIGINAL_SIX_RECOMPILED_SETTERS_DOLPHIN_MATCH', 'cases': 8, 'refusalRollbackCases': 8,
          'loweringSha256': sha(output / 'lowering.json'), 'originalProofSha256': sha(proof_path),
          'executableSha256': sha(exe), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Native executes six original generated setters from the full module with caller-supplied zero arguments/LRs.',
                     'Dolphin executes the original caller sequence; native diagnostic supplies those arguments rather than executing the enclosing OSInit function.',
                     'Reset-only adapter refuses nonzero writes, EE=1, user mode and invalid indices with no register-state mutation.',
                     'Counting, interrupts, context restores/reads/aliases and full post-timebase boot remain unverified; live policy still retained.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS six original recompiled setters:8Dolphin observations/8refusal rollback cases; counting and live boot still unverified')

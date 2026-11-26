"""Compare whole compiled GetID calls and two transaction-failure mutations."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'exi-getid-native'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
execution_path = output / 'execution.json'
execution = json.loads(execution_path.read_text())
assert execution['builderSha256'] == sha(experiment / 'build_exi_getid_native.py')
for path, digest in execution['sourceHashes'].items():
    assert sha(Path(path)) == digest
for name, digest in execution['headerHashes'].items():
    assert sha(experiment / name) == digest
for record in execution['records']:
    for path_key, hash_key in [('inputSource', 'inputSha256'), ('source', 'sourceSha256'), ('object', 'objectSha256')]:
        assert sha(Path(record[path_key])) == record[hash_key]
assert len(execution['records']) == 125 and sum(row['changed'] for row in execution['records']) == 2
assert execution['baseLoweringSha256'] == sha(private / 'mass-exi-select-boot/lowering.json')
subprocess.run(['python3', str(experiment / 'verify_exi_getid_dolphin.py')], check=True)
subprocess.run(['python3', str(experiment / 'verify_di_config_dolphin.py')], check=True)
oracle_path = private / 'dolphin-exi-getid/comparison.json'
assert execution['oracleSha256'] == sha(oracle_path)
assert execution['diOracleSha256'] == sha(private / 'dolphin-di-config/comparison.json')
oracle = json.loads(oracle_path.read_text())
exe = output / 'exi-getid-probe'
assert execution['executableSha256'] == sha(exe)
def run(mode):
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', mode], capture_output=True, text=True, timeout=30)
    (output / (mode + '.log')).write_text(result.stdout + result.stderr)
    rows = [list(map(int, line.split()[1:])) for line in result.stdout.splitlines() if line.startswith('GETID_CASE ')]
    phases = [list(map(int, line.split()[1:])) for line in result.stdout.splitlines() if line.startswith('GETID_PHASE ')]
    return result, rows, phases
expected = [[row['index'], row['returnValue'], row['destinationAfter'], row['csrBefore'], row['csrAfter'],
             row['causeBefore'], row['causeAfter'], row['controlAfter'], row['dataAfter'], row['cachedIdAfter'], *row['ecbAfter']]
            for row in oracle['observations']]
expected_phases = [[row['index'], phase['writtenControl'], phase['controlAfter'], phase['csrAfter'], phase['dataAfter']]
                   for row in oracle['observations'] for phase in row['phases']]
normal, rows, phases = run('normal')
assert normal.returncode == 0 and rows == expected and phases == expected_phases
lost, lost_rows, lost_phases = run('lost')
assert lost.returncode == 20 and not lost_rows and 'GetID instruction budget exceeded' in lost.stderr
wrong, wrong_rows, wrong_phases = run('wrong')
assert wrong.returncode == 0 and len(wrong_rows) == 16
differences = sum(a != b for a, b in zip(wrong_rows, expected))
assert differences == 16 and all(row[2] == 1 for row in wrong_rows)
guards, _, _ = run('guards')
assert guards.returncode == 0 and 'GETID_GUARDS 8' in guards.stdout
report = {'result': 'WHOLE_NATIVE_GETID16_AND32_PHASES_MATCH_ORIGINAL', 'cases': 16, 'phaseSnapshots': 32,
          'statePreservingRefusals': 8, 'lostCompletionDetected': True, 'wrongResponseDifferences': differences,
          'executionSha256': sha(execution_path), 'oracleSha256': sha(oracle_path), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Prepared whole GetID0/2 on measured None255 configuration, NI0/1 repeats; not full game startup or physical Wii.',
                     'Before/final CSR-PI/control/data/cache/ECB/ID-return and32phase snapshots compared; not all CPU registers/timing.',
                     'Measured DI config1 read-only adaptation, shared existing EXI CSR and PI storage; unsupported MMIO refused.',
                     'Original SDK functions remain compiled; polling budget/quiescent callback adapter, not automatic IRQ delivery.',
                     'Separate whole-call profile only; native boot integration/menu/first frame remain pending.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS whole original GetID16/32phases; lost-completion detected/wrong-response16/refusals8')

"""Audit only the ICE/immutable-image extension, retaining previous proofs and release invariants."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
native = Path('work/private-game/static-recomp/mass-icache')
output = Path('work/private-game/static-recomp/dolphin-icache-probe')
base = Path('work/private-game/static-recomp/mass-fpscr-translated')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
lowering = json.loads((native / 'lowering.json').read_text())
boot = json.loads((native / 'boot.json').read_text())
check = json.loads((native / 'icache-check.json').read_text())
assert lowering['result'] == check['result'] == 'PASS'
assert len(lowering['changes']) == 7 and len(lowering['records']) == 125
assert sum(record['modified'] for record in lowering['records']) == 2
assert lowering['adapterSha256'] == sha(experiment / 'icache_adapter.h')
assert lowering['scriptSha256'] == sha(experiment / 'build_icache.py')
assert lowering['baseLoweringSha256'] == sha(base / 'lowering.json')
assert boot['executableSha256'] == check['executableSha256'] == sha(native / 'openshsm-mass-boot')
assert check['scriptSha256'] == sha(experiment / 'verify_icache.py')
assert check['cases'] == 9 and check['originalIcEnableCases'] == 2
assert boot['wrapperSha256'] == sha(experiment / 'icache_boot.cpp')
assert boot['fpscrWrapperSha256'] == sha(experiment / 'fpscr_boot.cpp')
assert boot['baseWrapperSha256'] == sha(experiment / 'mass_boot.cpp')
assert boot['policySha256'] == sha(native / 'boot-quarantine.tsv') == sha(base / 'boot-quarantine.tsv')
for record in lowering['records']:
    source = Path(record['directory']) / record['file']
    prior = Path(record['inputDirectory']) / record['file']
    assert record['sourceSha256'] == sha(source) and record['inputSha256'] == sha(prior)
    assert record['objectSha256'] == sha(Path(str(source) + '.o'))
    if record['modified']:
        old, new = prior.read_text().splitlines(), source.read_text().splitlines()
        changes = [change for change in lowering['changes'] if change['file'] == record['file']]
        assert len(old) == len(new) and sum(before != after for before, after in zip(old, new)) == len(changes)
        assert all(any(change['priorLowering'] == before.strip() and change['adapterLowering'] == after.strip() for change in changes)
                   for before, after in zip(old, new) if before != after)
capture = json.loads((output / 'boot-dolphin.json').read_text(encoding='utf-8-sig'))
assert capture['scriptSha256'].lower() == sha(experiment / 'run_dolphin_probe.ps1')
subprocess.run(['python3', str(experiment / 'verify_dolphin_probe.py'), '--icache'], check=True)
subprocess.run(['python3', str(experiment / 'audit_dolphin_probe.py')], check=True)
comparison = json.loads((output / 'comparison.json').read_text())
assert comparison['measurementBoundary'] == '0x80212F8C/before DCEnable mtspr'
report = {'result': 'PASS_WITH_SCOPE_LIMITS', 'iceOriginalBootReadback': '0x8000',
          'overriddenSites': 7, 'modifiedBatches': 2, 'reusedObjects': 123, 'contractCases': 9,
          'comparisonSha256': sha(output / 'comparison.json'), 'releaseUnchanged': True,
          'next': 'Verify DCEnable/data-cache coherence contract and remaining cache/L2/OS initialization; no success stubs.',
          'limits': comparison['limits'] + check['limits']}
(output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS scoped ICE audit: original enable/boot state and immutable-image refusals; next DCEnable')

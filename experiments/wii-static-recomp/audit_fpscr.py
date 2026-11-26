"""Audit the mtfsf experiment without promoting partial PPC/paired evidence to game acceptance."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/mass-fpscr')
lowering = json.loads((output / 'lowering.json').read_text())
boot = json.loads((output / 'boot.json').read_text())
check = json.loads((output / 'fpscr-check.json').read_text())
initializer = json.loads((output / 'fpr-init.json').read_text())
comparison = json.loads((output / 'boot-original-comparison.json').read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert lowering['result'] == check['result'] == 'PASS'
assert len(lowering['changes']) == 4 and len(lowering['records']) == 125
assert sum(record['modified'] for record in lowering['records']) == 2
assert lowering['adapterSha256'] == sha(experiment / 'fpscr_adapter.h')
assert lowering['scriptSha256'] == sha(experiment / 'build_fpscr.py')
assert lowering['baseObjectsSha256'] == sha(Path('work/private-game/static-recomp/mass-current/objects.json'))
assert lowering['cacheLoweringSha256'] == sha(Path('work/private-game/static-recomp/mass-cache/lowering.json'))
for record in lowering['records']:
    directory = Path(record['directory'])
    source = directory / record['file']
    assert record['sourceSha256'] == sha(source)
    assert record['objectSha256'] == sha(directory / (record['file'] + '.o'))
    prior_directory = Path('work/private-game/static-recomp/mass-cache' if record['modified'] else record['directory'])
    original = prior_directory / record['file']
    assert record['inputSha256'] == sha(original)
    if record['modified']:
        old, new = original.read_text().splitlines(), source.read_text().splitlines()
        assert len(old) == len(new)
        changes = [change for change in lowering['changes'] if change['file'] == record['file']]
        assert sum(before != after for before, after in zip(old, new)) == len(changes)
        assert all(any(change['priorLowering'] == before.strip() and change['adapterLowering'] == after.strip() for change in changes)
                   for before, after in zip(old, new) if before != after)
exe = sha(output / 'openshsm-mass-boot')
assert boot['executableSha256'] == check['executableSha256'] == initializer['executableSha256'] == exe
assert boot['wrapperSha256'] == sha(experiment / 'fpscr_boot.cpp')
assert boot['baseWrapperSha256'] == sha(experiment / 'mass_boot.cpp')
assert boot['policySha256'] == sha(output / 'boot-quarantine.tsv')
assert check['scriptSha256'] == sha(experiment / 'verify_fpscr.py')
assert initializer['scriptSha256'] == sha(experiment / 'verify_fpr_init.py')
assert check['originalInstructionCases'] == 416 and check['syntheticMaskRecordCases'] == 512
assert check['exactUnicornCases'] == 327 and len(check['oracleDivergences']) == 601
assert check['refusalCases'] == 2 and check['malformedInputCases'] == 7
assert initializer['result'] == 'PASS_WITH_SCOPE_LIMITS' and initializer['originalPpcNonPairedCases'] == 4
assert comparison['result'] == 'PARTIAL_VERIFICATION' and comparison['originalInstructionsExecuted'] == 81
assert comparison['fprFpscrCrEntrySnapshotsMatch'] == 8
assert comparison['bootReportSha256'] == sha(output / 'boot.json')
assert 'BOOT_BOUNDARY pc=802130e0' in boot['stdout']
subprocess.run(['python3', str(experiment / 'audit_cache.py')], check=True)
report = {'result': 'PASS_WITH_SCOPE_LIMITS', 'mtfsfSites': 4, 'modifiedBatches': 2, 'reusedObjects': 123,
          'exactInstructionOracleCases': 327, 'retainedOracleDivergences': 601, 'originalPpcNonPairedInitializerCases': 4,
          'independentlyExecutedBootPrefix': 81, 'nativeBoundary': 'ICEnable/802130E0',
          'fullBootPrefixVerified': False, 'releaseUnchanged': True,
          'next': 'Obtain a paired-single capable independent oracle; verify PSE=1 original bootstrap, then HID0 cache enable/OS initialization.',
          'limits': check['limits'] + initializer['limits'] + comparison['limits']}
(output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS scoped audit:4 mtfsf lowerings; full paired bootstrap remains UNVERIFIED; release unchanged')

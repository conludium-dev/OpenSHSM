"""Audit original NI setter and pre-effect guards before allowing scoped activation."""
from pathlib import Path
import hashlib
import json
import subprocess
from ni_guard_lowering import lower

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'mass-ni-guard'
base = private / 'mass-frsp'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_ni_guard.py')], check=True)
proof_path = private / 'ni-guard/comparison.json'
proof = json.loads(proof_path.read_text())
lowering = json.loads((output / 'lowering.json').read_text())
assert lowering['baseLoweringSha256'] == sha(base / 'lowering.json')
for key, filename in [('adapterSha256', 'ni_guard.h'), ('frspAdapterSha256', 'frsp_adapter.h'),
                      ('probeSha256', 'ni_set_probe.h'), ('scriptSha256', 'build_ni_guard.py'),
                      ('lowererSha256', 'ni_guard_lowering.py'), ('baseBuilderSha256', 'build_branch.py')]:
    assert lowering[key] == sha(experiment / filename)
assert lowering['seedHeaderSha256'] == sha(output / 'loader-bat-seed.h') == sha(base / 'loader-bat-seed.h')
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
metadata = json.loads((base / 'lowering.json').read_text())
assert len(metadata['records']) == len(lowering['records']) == 125
setters, guards, addresses = 0, 0, set()
for old, record in zip(metadata['records'], lowering['records']):
    source = Path(old['directory']) / old['file']
    assert sha(source) == old['sourceSha256'] and old['file'] == record['file']
    expected, changes = lower(source.read_text(), original)
    target = Path(record['directory']) / record['file']
    assert target.read_text() == expected and changes == record['changes']
    assert sha(target) == record['sourceSha256'] and sha(Path(str(target) + '.o')) == record['objectSha256']
    for change in changes:
        addresses.add(change['address'])
        if change['kind'] == 'setter':
            assert change['address'] == '0x80210830'
            setters += 1
        else:
            assert change['after'].endswith(change['before'])
            guards += 1
assert setters == lowering['setterSites'] and setters + guards == lowering['sites']
boot = json.loads((output / 'boot.json').read_text())
exe = output / 'openshsm-mass-boot'
assert boot['executableSha256'] == sha(exe) and boot['wrapperSha256'] == sha(output / 'boot-wrapper.cpp')
assert boot['loweringSha256'] == sha(output / 'lowering.json')
observations = json.loads((private / 'dolphin-frsp-flags/comparison.json').read_text())['observations']
selected = [row for row in observations if row['fpscrBefore'] & 4]
assert len(selected) == 128
execution = subprocess.run([str(exe), '--ni-set-check'], input=''.join(f"{row['fpscrBefore'] & ~4}\n" for row in selected),
                           capture_output=True, text=True, timeout=30)
assert execution.returncode == 0 and list(map(int, execution.stdout.splitlines())) == [row['fpscrBefore'] for row in selected]
prefix = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(private / 'mass-l2/boot-quarantine.tsv')],
                        capture_output=True, text=True, timeout=30)
baseline = private / 'mass-timebase/boot.json'
assert prefix.returncode == 7 and prefix.stdout == json.loads(baseline.read_text())['stdout']
assert 'BOOT_BOUNDARY pc=80210830 lr=802113e8 msr=2030' in boot['stdout']
report = {'result': 'NI_SETTER_FULL_MODULE_STATE_AND_GENERATED_FP_GUARDS_VERIFIED',
          'originalSetterObservations': 128, 'setterRefusalRollbackCases': 8,
          'guardPolicyCases': proof['policyCases'], 'setterSites': setters, 'guardSites': guards,
          'uniqueFpAddresses': len(addresses), 'loweringSha256': sha(output / 'lowering.json'),
          'proofSha256': sha(proof_path), 'bootSha256': sha(output / 'boot.json'),
          'executableSha256': sha(exe), 'preTimebaseBaselineSha256': sha(baseline), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Original setter FPSCR observations plus native full-function return/register preservation contract.',
                     'NI1 traps before unverified FP effects; attempted instruction counter may increment before guard.',
                     'NI0 retains existing backend behavior; no full FPU claim or physical Wii proof.',
                     'Guards cover generated IR, not undiscovered code/interpreter fallback; fallback remains strict.']}
(output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'PASS NI setter128observations/fullmodule; {guards}FPguard sites; pretimebase retained; activation separate')

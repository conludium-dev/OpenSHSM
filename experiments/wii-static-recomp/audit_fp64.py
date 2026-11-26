"""Check full-module FP64 routing and original memcpy under both NI modes."""
from pathlib import Path
import base64
import hashlib
import json
import subprocess
from fp64_lowering import lower

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'mass-fp64'
base = private / 'mass-code-write-observer'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_fp64.py')], check=True)
subprocess.run(['python3', str(experiment / 'verify_template_modes_dolphin.py')], check=True)
windows_path = private / 'dolphin-fp64/windows-comparison.json'
windows = json.loads(windows_path.read_text())
assert windows['cases'] == 320 and windows['refusalRollbackCases'] == 9 and windows['zeroRaContracts'] == 3
assert windows['oracleSha256'] == sha(private / 'dolphin-fp64/comparison.json')
assert windows['adapterSha256'] == sha(experiment / 'fp64_transfer.h')
assert windows['scriptSha256'] == sha(experiment / 'verify_fp64_windows.py')
assert windows['executableSha256'] == [sha(private / 'dolphin-fp64' / f'fp64-{name}-windows.exe') for name in ('probe', 'contract')]
metadata = json.loads((base / 'lowering.json').read_text())
lowering = json.loads((output / 'lowering.json').read_text())
assert lowering['baseLoweringSha256'] == sha(base / 'lowering.json')
for key, filename in [('adapterSha256', 'fp64_transfer.h'), ('scriptSha256', 'build_fp64.py'),
                      ('lowererSha256', 'fp64_lowering.py'), ('baseBuilderSha256', 'build_branch.py'),
                      ('baseProbeSha256', 'template_copy_probe.h')]:
    assert lowering[key] == sha(experiment / filename)
assert lowering['seedHeaderSha256'] == sha(output / 'loader-bat-seed.h') == sha(base / 'loader-bat-seed.h')
probe = (experiment / 'template_copy_probe.h').read_text().replace('experiment_template_copy_probe', 'experiment_fp64_template_copy_probe')
probe = probe.replace('index * 256', '(index + (ni ? 16 : 0)) * 256')
assert (output / 'fp64-template-probe.h').read_text() == probe
assert lowering['probeSha256'] == sha(output / 'fp64-template-probe.h')
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert len(metadata['records']) == len(lowering['records']) == 125
addresses = set()
for old, record in zip(metadata['records'], lowering['records']):
    source = Path(old['directory']) / old['file']
    assert sha(source) == old['sourceSha256'] and old['file'] == record['file']
    expected, changes = lower(source.read_text(), original)
    target = Path(record['directory']) / record['file']
    assert target.read_text() == expected and changes == record['changes']
    assert sha(target) == record['sourceSha256'] and sha(Path(str(target) + '.o')) == record['objectSha256']
    addresses.update(change['address'] for change in changes)
assert lowering['sites'] == 15340 and len(addresses) == 10836
boot = json.loads((output / 'boot.json').read_text())
exe = output / 'openshsm-mass-boot'
policy = private / 'mass-ni-guard/boot-quarantine.tsv'
assert boot['executableSha256'] == sha(exe) and boot['wrapperSha256'] == sha(output / 'boot-wrapper.cpp')
assert boot['loweringSha256'] == sha(output / 'lowering.json') and boot['policySha256'] == sha(policy)
measurement = private / 'dolphin-template-modes'
capture = json.loads((measurement / 'fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
data = base64.b64decode(capture['data'])
records = json.loads((measurement / 'generation.json').read_text())['records']
for ni in (0, 1):
    result = subprocess.run([str(exe), f'--fp64-template-ni{ni}'], capture_output=True, text=True, timeout=30)
    (output / f'original-template-ni{ni}.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, (result.returncode, result.stderr)
    rows = result.stdout.splitlines()
    selected = [record for record in records if record['ni'] == ni]
    assert len(rows) == len(selected) == 16
    for native_index, (row, record) in enumerate(zip(rows, selected)):
        index, returned, payload = row.split()
        assert int(index) == native_index and int(returned) == record['destination']
        offset = record['index'] * 736 + 192
        assert bytes.fromhex(payload) == data[offset:offset + 152]
prefix = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(private / 'mass-l2/boot-quarantine.tsv')],
                        capture_output=True, text=True, timeout=30)
baseline = private / 'mass-timebase/boot.json'
assert prefix.returncode == 7 and prefix.stdout == json.loads(baseline.read_text())['stdout']
live = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)],
                      capture_output=True, text=True, timeout=30)
assert live.returncode == 7 and 'write instruction=802119a8 address=80211c08 value=38600000 length=4' in live.stdout
(output / 'live-replay.log').write_text(live.stdout + live.stderr)
report = {'result': 'FP64_FULL_MODULE_AND_ORIGINAL_MEMCPY_NI0_NI1_VERIFIED_CODE_POLICY_UNCHANGED',
          'originalInstructionCases': 320, 'refusalRollbackCases': 9, 'zeroRaContracts': 3,
          'windowsHelperCases': 320, 'windowsProofSha256': sha(windows_path),
          'loweredSites': 15340, 'uniqueAddresses': 10836, 'originalMemcpyCases': 32, 'copiedBytes': 4864,
          'loweringSha256': sha(output / 'lowering.json'), 'executableSha256': sha(exe),
          'bootSha256': sha(output / 'boot.json'), 'instructionProofSha256': sha(private / 'dolphin-fp64/comparison.json'),
          'memcpyProofSha256': sha(measurement / 'comparison.json'), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Six FP64 forms on existing BAT/cache; other FP operations keep NI guards.',
                     'Full original memcpy32template fixtures match bytes/return atNI0/NI1; not full OS exception loop.',
                     'Mutable template/code writes still refused; old NI1-refusing module preserved as historical evidence.',
                     'New live post-clock CPU/memory endpoint, vector relocation/dispatch, physical Wii/menu/game unverified.']}
(output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS FP64full125module/15340sites/320originalcases; original memcpyNI0-NI1/32cases/4864bytes; codewrite unchanged')

"""Verify exact store observation through unchanged policies and retained boot prefix."""
from pathlib import Path
import hashlib
import json
import subprocess
from code_write_lowering import lower

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'mass-code-write-observer'
base = private / 'mass-ni-guard'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
metadata = json.loads((base / 'lowering.json').read_text())
lowering = json.loads((output / 'lowering.json').read_text())
assert lowering['sites'] == 1 and lowering['baseLoweringSha256'] == sha(base / 'lowering.json')
for key, filename in [('adapterSha256', 'code_write_observer.h'), ('scriptSha256', 'build_code_write_observer.py'),
                      ('lowererSha256', 'code_write_lowering.py'), ('baseBuilderSha256', 'build_branch.py')]:
    assert lowering[key] == sha(experiment / filename)
assert lowering['seedHeaderSha256'] == sha(output / 'loader-bat-seed.h') == sha(base / 'loader-bat-seed.h')
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert len(metadata['records']) == len(lowering['records']) == 125
for old, record in zip(metadata['records'], lowering['records']):
    source = Path(old['directory']) / old['file']
    assert sha(source) == old['sourceSha256'] and old['file'] == record['file']
    expected, changes = lower(source.read_text(), original)
    target = Path(record['directory']) / record['file']
    assert target.read_text() == expected and record['changes'] == changes
    assert sha(target) == record['sourceSha256'] and sha(Path(str(target) + '.o')) == record['objectSha256']
boot = json.loads((output / 'boot.json').read_text())
exe = output / 'openshsm-mass-boot'
policy = base / 'boot-quarantine.tsv'
assert boot['executableSha256'] == sha(exe) and boot['wrapperSha256'] == sha(output / 'boot-wrapper.cpp')
assert boot['loweringSha256'] == sha(output / 'lowering.json') and boot['policySha256'] == sha(policy)
expected_reason = 'write instruction=802119a8 address=80211c08 value=38600000 length=4'
replay = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)],
                        capture_output=True, text=True, timeout=30)
assert replay.returncode == 7 and expected_reason in replay.stdout and expected_reason in boot['stdout']
(output / 'live-replay.log').write_text(replay.stdout + replay.stderr)
prefix = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(private / 'mass-l2/boot-quarantine.tsv')],
                        capture_output=True, text=True, timeout=30)
baseline = private / 'mass-timebase/boot.json'
assert prefix.returncode == 7 and prefix.stdout == json.loads(baseline.read_text())['stdout']
report = {'result': 'EXACT_ORIGINAL_STORE_DIAGNOSTIC_CONFIRMED_WRITE_POLICY_UNCHANGED',
          'instruction': '0x802119a8', 'target': '0x80211c08', 'value': '0x38600000', 'length': 4,
          'loweringSha256': sha(output / 'lowering.json'), 'bootSha256': sha(output / 'boot.json'),
          'executableSha256': sha(exe), 'policySha256': sha(policy), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Observer calls unchanged BAT write and augments its refusal message; no code-write allowance.',
                     'Full post-clock CPU/memory endpoint unverified; pre-timebase state matches retained baseline.',
                     'Exact native attempt confirmed; original template mutation/copy/dispatch requires independent evidence.']}
(output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS exactstore802119A8→80211C08/value38600000; original write guard/policy unchanged, pretimebase retained')

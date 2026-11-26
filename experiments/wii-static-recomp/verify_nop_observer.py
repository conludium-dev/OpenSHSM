"""Check the exact second store observation and unchanged native write policy."""
from pathlib import Path
import hashlib
import json
import subprocess
from nop_observer_lowering import lower

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'mass-nop-observer'
base = private / 'mass-template-patch'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
metadata = json.loads((base / 'lowering.json').read_text())
lowering = json.loads((output / 'lowering.json').read_text())
assert lowering['sites'] == 1 and lowering['baseLoweringSha256'] == sha(base / 'lowering.json')
for key, filename in [('adapterSha256', 'template_patch.h'), ('scriptSha256', 'build_nop_observer.py'),
                      ('lowererSha256', 'nop_observer_lowering.py'), ('baseBuilderSha256', 'build_branch.py'),
                      ('observerBuilderSha256', 'build_code_write_observer.py')]:
    assert lowering[key] == sha(experiment / filename)
for name, digest in lowering['privateHeaderSha256'].items():
    assert digest == sha(output / name) == sha(base / name)
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert len(metadata['records']) == len(lowering['records']) == 125
for old, record in zip(metadata['records'], lowering['records']):
    source = Path(old['directory']) / old['file']
    assert sha(source) == old['sourceSha256'] and old['file'] == record['file']
    expected, changes = lower(source.read_text(), original)
    target = Path(record['directory']) / record['file']
    assert target.read_text() == expected and changes == record['changes']
    assert sha(target) == record['sourceSha256'] and sha(Path(str(target) + '.o')) == record['objectSha256']
boot = json.loads((output / 'boot.json').read_text())
exe = output / 'openshsm-mass-boot'
policy = private / 'mass-ni-guard/boot-quarantine.tsv'
assert boot['executableSha256'] == sha(exe) and boot['wrapperSha256'] == sha(output / 'boot-wrapper.cpp')
assert boot['loweringSha256'] == sha(output / 'lowering.json') and boot['policySha256'] == sha(policy)
replay = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)],
                        capture_output=True, text=True, timeout=30)
expected = 'write instruction=80211a30 address=80211bf8 value=60000000 length=4'
assert replay.returncode == 7 and expected in boot['stdout'] and expected in replay.stdout
(output / 'live-replay.log').write_text(replay.stdout + replay.stderr)
prefix = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(private / 'mass-l2/boot-quarantine.tsv')],
                        capture_output=True, text=True, timeout=30)
assert prefix.returncode == 7 and prefix.stdout == json.loads((private / 'mass-timebase/boot.json').read_text())['stdout']
report = {'result': 'EXACT_SECOND_NOP_STORE_CONFIRMED_WRITE_POLICY_UNCHANGED',
          'instruction': '0x80211a30', 'address': '0x80211bf8', 'value': '0x60000000',
          'loweringSha256': sha(output / 'lowering.json'), 'bootSha256': sha(output / 'boot.json'),
          'executableSha256': sha(exe), 'policySha256': sha(policy), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Existing BAT write still refuses; observer only appends exact parameters.',
                     'Previous measured exception-number patch remains enabled with38compiled-template instruction guards.',
                     'NOP native adaptation and full original vector initialization/post-clock endpoint/menu remain unverified.']}
(output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS exactsecondstore80211A30→80211BF8/value60000000; NOPwrite stillblocked, policy/pretimebaseline unchanged')

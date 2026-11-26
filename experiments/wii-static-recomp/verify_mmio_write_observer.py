"""Reproduce exact MMIO refusal and validate unchanged predecessor artifacts."""
from pathlib import Path
import hashlib
import json
import subprocess
from mmio_write_lowering import lower

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
base, output = private / 'mass-template-reset', private / 'mass-mmio-observer'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
metadata = json.loads((base / 'lowering.json').read_text())
lowering = json.loads((output / 'lowering.json').read_text())
assert lowering['sites'] == 10 and lowering['baseLoweringSha256'] == sha(base / 'lowering.json')
for key, filename in [('adapterSha256', 'mmio_write_observer.h'), ('scriptSha256', 'build_mmio_write_observer.py'),
                      ('lowererSha256', 'mmio_write_lowering.py'), ('baseBuilderSha256', 'build_branch.py'),
                      ('observerBuilderSha256', 'build_code_write_observer.py'), ('nopBuilderSha256', 'build_nop_observer.py')]:
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
exe, policy = output / 'openshsm-mass-boot', private / 'mass-ni-guard/boot-quarantine.tsv'
assert boot['executableSha256'] == sha(exe) and boot['wrapperSha256'] == sha(output / 'boot-wrapper.cpp')
assert boot['loweringSha256'] == sha(output / 'lowering.json') and boot['policySha256'] == sha(policy)
replay = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)], capture_output=True, text=True, timeout=30)
needle = 'memory instruction=802175d0 address=cc003004 value=f0 length=4 physical=c003004'
assert replay.returncode == 7 and needle in replay.stdout and needle in boot['stdout']
(output / 'live-replay.log').write_text(replay.stdout + replay.stderr)
prefix = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(private / 'mass-l2/boot-quarantine.tsv')], capture_output=True, text=True, timeout=30)
assert prefix.returncode == 7 and prefix.stdout == json.loads((private / 'mass-timebase/boot.json').read_text())['stdout']
stale = subprocess.run([str(exe), '--template-stale-check'], capture_output=True, text=True, timeout=30)
assert stale.returncode == 0 and stale.stdout == 'TEMPLATE_STALE_GUARDS 38\n'
report = {'result': 'EXACT_ORIGINAL_MMIO_STORE_REFUSED_POLICY_UNCHANGED', 'observedStoreSites': 10,
          'instruction': '0x802175d0', 'opcode': '0x90a43004', 'virtualTarget': '0xcc003004',
          'physicalTarget': '0x0c003004', 'value': '0xf0', 'length': 4,
          'loweringSha256': sha(output / 'lowering.json'), 'bootSha256': sha(output / 'boot.json'),
          'executableSha256': sha(exe), 'policySha256': sha(policy), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Original DOL opcode and exact native attempted store; diagnostic delegates unchanged writer.',
                     'Hardware register semantics, original write behavior and native implementation unverified.',
                     'Whole vector/table/post-clock endpoint, relocated handlers and menu unverified.']}
(output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS exactMMIOstore802175D0→CC003004/physical0C003004/valueF0; no newpermissions')

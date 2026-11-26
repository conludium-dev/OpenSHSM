"""Verify all observed table/reset stores and the exact protected reset attempt."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess
from table_write_lowering import lower

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'mass-table-observer'
base = private / 'mass-template-nop'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
metadata = json.loads((base / 'lowering.json').read_text())
lowering = json.loads((output / 'lowering.json').read_text())
assert lowering['sites'] == 17 and lowering['baseLoweringSha256'] == sha(base / 'lowering.json')
for key, filename in [('adapterSha256', 'table_write_observer.h'), ('scriptSha256', 'build_table_write_observer.py'),
                      ('lowererSha256', 'table_write_lowering.py'), ('baseBuilderSha256', 'build_branch.py'),
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
header = struct.unpack('>64I', original[:256])
address = 0x80211b0c
section = next(i for i in range(7) if header[18 + i] <= address < header[18 + i] + header[36 + i])
opcode = struct.unpack_from('>I', original, header[section] + address - header[18 + section])[0]
assert opcode == 0x937c0000
boot = json.loads((output / 'boot.json').read_text())
exe = output / 'openshsm-mass-boot'
policy = private / 'mass-ni-guard/boot-quarantine.tsv'
assert boot['executableSha256'] == sha(exe) and boot['wrapperSha256'] == sha(output / 'boot-wrapper.cpp')
assert boot['loweringSha256'] == sha(output / 'lowering.json') and boot['policySha256'] == sha(policy)
replay = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)], capture_output=True, text=True, timeout=30)
needle = 'table instruction=80211b0c address=80211c08 physical=211c08 value=38600000 protected=800067a0 size=3d1bc0'
assert replay.returncode == 7 and needle in replay.stdout and needle in boot['stdout']
(output / 'live-replay.log').write_text(replay.stdout + replay.stderr)
prefix = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(private / 'mass-l2/boot-quarantine.tsv')],
                        capture_output=True, text=True, timeout=30)
assert prefix.returncode == 7 and prefix.stdout == json.loads((private / 'mass-timebase/boot.json').read_text())['stdout']
report = {'result': 'THIRD_WRITE_IS_TEMPLATE_ID_RESET_NOT_HANDLER_TABLE_FAILURE',
          'observedStoreSites': 17, 'instruction': hex(address), 'opcode': hex(opcode),
          'virtualTarget': '0x80211c08', 'physicalTarget': '0x00211c08', 'value': '0x38600000',
          'loweringSha256': sha(output / 'lowering.json'), 'bootSha256': sha(output / 'boot.json'),
          'executableSha256': sha(exe), 'policySha256': sha(policy), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Observed virtual/physical/image parameters through unchanged BAT writer; reset remains refused.',
                     'Static stw r27,0(r28) and native attempt match; original reset behavior still requires independent execution.',
                     'Complete real-vector/table contents and full post-clock endpoint/relocated handler/menu unverified.']}
(output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS exactthirdstore80211B0C resetsIDword80211C08→38600000;17storeobservations; no newpermissions')

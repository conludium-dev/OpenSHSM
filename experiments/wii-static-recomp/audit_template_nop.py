"""Verify the measured NOP store on existing cache with protected template execution."""
from pathlib import Path
import base64
import hashlib
import json
import re
import struct
import subprocess
from template_nop_lowering import lower

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'mass-template-nop'
base = private / 'mass-template-patch'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_nop_copy_dolphin.py')], check=True)
lowering = json.loads((output / 'lowering.json').read_text())
metadata = json.loads((base / 'lowering.json').read_text())
assert lowering['sites'] == 1 and lowering['baseLoweringSha256'] == sha(base / 'lowering.json')
for key, filename in [('adapterSha256', 'template_nop.h'), ('scriptSha256', 'build_template_nop.py'),
                      ('lowererSha256', 'template_nop_lowering.py'), ('baseBuilderSha256', 'build_branch.py'),
                      ('observerBuilderSha256', 'build_code_write_observer.py'), ('nopObserverBuilderSha256', 'build_nop_observer.py')]:
    assert lowering[key] == sha(experiment / filename)
for name in ('loader-bat-seed.h', 'fp64-template-probe.h'):
    assert lowering['privateHeaderSha256'][name] == sha(output / name) == sha(base / name)
probe = (base / 'mutable-template-probe.h').read_text().replace('#include "template_patch.h"', '#include "template_nop.h"')
probe = probe.replace('        experiment_template_patch(context, 0x80211c08, value, 0x802119a8);',
                      '        experiment_template_patch(context, 0x80211c08, value, 0x802119a8);\n        experiment_template_nop(context, 0x80211bf8, 0x60000000, 0x80211a30);')
assert (output / 'mutable-template-probe.h').read_text() == probe
assert lowering['privateHeaderSha256']['mutable-template-probe.h'] == sha(output / 'mutable-template-probe.h')
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert len(metadata['records']) == len(lowering['records']) == 125
for old, record in zip(metadata['records'], lowering['records']):
    source = Path(old['directory']) / old['file']
    assert sha(source) == old['sourceSha256'] and old['file'] == record['file']
    expected, changes = lower(source.read_text(), original)
    target = Path(record['directory']) / record['file']
    assert target.read_text() == expected and changes == record['changes']
    assert sha(target) == record['sourceSha256'] and sha(Path(str(target) + '.o')) == record['objectSha256']
contract_body = (experiment / 'template_patch_contract.cpp').read_text().replace('"template_patch.h"', '"template_nop.h"')
contract_body = contract_body.replace('        experiment_template_patch(context, 0x80211c08, 0x38600000 | index, 0x802119a8);',
                                      '        experiment_template_patch(context, 0x80211c08, 0x38600000 | index, 0x802119a8);\n        experiment_template_nop(context, 0x80211bf8, 0x60000000, 0x80211a30);')
contract_body = contract_body.replace('experiment_template_patch(context, address, value, instruction)', 'experiment_template_nop(context, address, value, instruction)')
def refusal(match):
    address, value, instruction = (int(word, 16) for word in match.groups())
    address = 0x80211bf8 if address == 0x80211c08 else address
    value = 0x60000000 if value == 0x38600000 else (0x60000001 if value == 0x60000000 else value)
    instruction = 0x80211a30 if instruction == 0x802119a8 else 0x80211a34
    return f'refused({hex(address)}, {hex(value)}, {hex(instruction)})'
contract_body = re.sub(r'refused\((0x[0-9a-f]+), (0x[0-9a-f]+), (0x[0-9a-f]+)\)', refusal, contract_body)
contract_source = output / 'nop-contract.cpp'
contract_source.write_text(contract_body)
header = struct.unpack('>64I', original[:256])
section = next(index for index in range(7) if header[18 + index] <= 0x80211ba0 < header[18 + index] + header[36 + index])
offset = header[section] + 0x80211ba0 - header[18 + section]
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
contract_exe = output / 'nop-contract'
build = subprocess.run(['clang++', '-std=c++20', '-O2', '-I', str(experiment), '-I', str(output),
                        '-I', str(upstream / 'nWiiRuntime/include'), str(contract_source), '-o', str(contract_exe)],
                       capture_output=True, text=True, timeout=30)
assert build.returncode == 0, build.stderr
contract = subprocess.run([str(contract_exe)], input=original[offset:offset + 152].hex() + '\n', capture_output=True, text=True, timeout=30)
assert contract.returncode == 0 and contract.stdout == 'TEMPLATE_CONTRACT writes=16 guards=10 entries=38\n', contract
boot = json.loads((output / 'boot.json').read_text())
exe = output / 'openshsm-mass-boot'
policy = private / 'mass-ni-guard/boot-quarantine.tsv'
assert boot['executableSha256'] == sha(exe) and boot['wrapperSha256'] == sha(output / 'boot-wrapper.cpp')
assert boot['loweringSha256'] == sha(output / 'lowering.json') and boot['policySha256'] == sha(policy)
stale = subprocess.run([str(exe), '--template-stale-check'], capture_output=True, text=True, timeout=30)
assert stale.returncode == 0 and stale.stdout == 'TEMPLATE_STALE_GUARDS 38\n'
measurement = private / 'dolphin-template-modes'
capture = json.loads((measurement / 'fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
data = base64.b64decode(capture['data'])
records = json.loads((measurement / 'generation.json').read_text())['records']
for ni in (0, 1):
    result = subprocess.run([str(exe), f'--mutable-template-ni{ni}'], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, (result.returncode, result.stderr)
    selected = [row for row in records if row['ni'] == ni]
    rows = result.stdout.splitlines()
    assert len(rows) == len(selected) == 16
    for native_index, (line, row) in enumerate(zip(rows, selected)):
        index, returned, payload = line.split()
        assert int(index) == native_index and int(returned) == row['destination']
        offset = row['index'] * 736 + 192
        assert bytes.fromhex(payload) == data[offset:offset + 152]
prefix = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(private / 'mass-l2/boot-quarantine.tsv')],
                        capture_output=True, text=True, timeout=30)
assert prefix.returncode == 7 and prefix.stdout == json.loads((private / 'mass-timebase/boot.json').read_text())['stdout']
live = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)], capture_output=True, text=True, timeout=30)
assert live.returncode == 7 and 'BOOT_BOUNDARY pc=80211a7c' in live.stdout
(output / 'live-replay.log').write_text(live.stdout + live.stderr)
report = {'result': 'SCOPED_NOP_STORE_PATCH_COPY_AND_STALE_ENTRY_GUARDS_VERIFIED_NEW_ENDPOINT_UNVERIFIED',
          'originalNopCases': 32, 'combinedNativeCopyCases': 32, 'copiedBytes': 4864,
          'refusalRollbackCases': 10, 'compiledStaleEntryRefusals': 38,
          'loweringSha256': sha(output / 'lowering.json'), 'bootSha256': sha(output / 'boot.json'),
          'nopOracleSha256': sha(private / 'dolphin-nop-copy/comparison.json'),
          'idOracleSha256': sha(measurement / 'comparison.json'), 'contractSourceSha256': sha(contract_source),
          'contractBaseSha256': sha(experiment / 'template_patch_contract.cpp'), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Two disjoint measured stores compose on sameMMU/cache; no blanket code-write allowance.',
                     'Native loop advances; complete copied real vectors/post-clock CPU-memory endpoint not independently accepted.',
                     'Template/relocated handler execution, further code writes/OS/IOS/GX/menu remain unverified.']}
(output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS scopedNOP32originalcases/32combinedcopies/10rollbackguards/38staleentries; newlive80211A7C endpoint unverified')

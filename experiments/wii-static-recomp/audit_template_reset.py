"""Verify scoped reset lowering, cached native copy, rollback and stale entries."""
from pathlib import Path
import base64
import hashlib
import json
import struct
import subprocess
from template_reset_lowering import lower

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
base, output = private / 'mass-table-observer', private / 'mass-template-reset'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_reset_copy_dolphin.py')], check=True)
metadata = json.loads((base / 'lowering.json').read_text())
lowering = json.loads((output / 'lowering.json').read_text())
assert lowering['sites'] == 1 and lowering['baseLoweringSha256'] == sha(base / 'lowering.json')
for key, filename in [('adapterSha256', 'template_reset.h'), ('scriptSha256', 'build_template_reset.py'),
                      ('lowererSha256', 'template_reset_lowering.py'), ('baseBuilderSha256', 'build_branch.py'),
                      ('observerBuilderSha256', 'build_code_write_observer.py'), ('nopObserverBuilderSha256', 'build_nop_observer.py')]:
    assert lowering[key] == sha(experiment / filename)
for name in ('loader-bat-seed.h', 'fp64-template-probe.h'):
    assert lowering['privateHeaderSha256'][name] == sha(output / name) == sha(base / name)
probe = (base / 'mutable-template-probe.h').read_text().replace('#include "template_nop.h"', '#include "template_reset.h"')
probe = probe.replace('        experiment_template_nop(context, 0x80211bf8, 0x60000000, 0x80211a30);',
                      '        experiment_template_nop(context, 0x80211bf8, 0x60000000, 0x80211a30);\n        experiment_template_reset(context, 0x80211c08, 0x38600000, 0x80211b0c);')
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

contract_body = (experiment / 'template_patch_contract.cpp').read_text().replace('"template_patch.h"', '"template_reset.h"')
contract_body = contract_body.replace('for (unsigned index = 0; index < 16; ++index)', 'for (unsigned index = 0; index < 32; ++index)')
contract_body = contract_body.replace('        experiment_template_patch(context, 0x80211c08, 0x38600000 | index, 0x802119a8);',
                                    '        context.fpscr = index >= 16 ? 4 : 0;\n        experiment_template_patch(context, 0x80211c08, 0x38600000 | (index & 15), 0x802119a8);\n        experiment_template_reset(context, 0x80211c08, 0x38600000, 0x80211b0c);')
contract_body = contract_body.replace('(0x38600000 | index)', '0x38600000').replace('pointer[107] != 15', 'pointer[107] != 0')
contract_body = contract_body.replace('experiment_template_patch(context, address, value, instruction)', 'experiment_template_reset(context, address, value, instruction)')
contract_body = contract_body.replace('0x802119a8);', '0x80211b0c);').replace('0x802119ac);', '0x80211b10);')
contract_body = contract_body.replace('0x38600000 | (index & 15), 0x80211b0c);', '0x38600000 | (index & 15), 0x802119a8);')
contract_body = contract_body.replace('TEMPLATE_CONTRACT writes=16', 'TEMPLATE_CONTRACT writes=32')
contract_source, contract_exe = output / 'reset-contract.cpp', output / 'reset-contract'
contract_source.write_text(contract_body)
header = struct.unpack('>64I', original[:256])
section = next(i for i in range(7) if header[18 + i] <= 0x80211ba0 < header[18 + i] + header[36 + i])
offset = header[section] + 0x80211ba0 - header[18 + section]
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
build = subprocess.run(['clang++', '-std=c++20', '-O2', '-I', str(experiment), '-I', str(output),
                        '-I', str(upstream / 'nWiiRuntime/include'), str(contract_source), '-o', str(contract_exe)], capture_output=True, text=True, timeout=30)
assert build.returncode == 0, build.stderr
contract = subprocess.run([str(contract_exe)], input=original[offset:offset + 152].hex() + '\n', capture_output=True, text=True, timeout=30)
assert contract.returncode == 0 and contract.stdout == 'TEMPLATE_CONTRACT writes=32 guards=10 entries=38\n', contract
boot = json.loads((output / 'boot.json').read_text())
exe, policy = output / 'openshsm-mass-boot', private / 'mass-ni-guard/boot-quarantine.tsv'
assert boot['executableSha256'] == sha(exe) and boot['wrapperSha256'] == sha(output / 'boot-wrapper.cpp')
assert boot['loweringSha256'] == sha(output / 'lowering.json') and boot['policySha256'] == sha(policy)
stale = subprocess.run([str(exe), '--template-stale-check'], capture_output=True, text=True, timeout=30)
assert stale.returncode == 0 and stale.stdout == 'TEMPLATE_STALE_GUARDS 38\n'
measurement = private / 'dolphin-reset-copy'
capture = json.loads((measurement / 'fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
data = base64.b64decode(capture['data'])
records = json.loads((measurement / 'generation.json').read_text())['records']
for ni in (0, 1):
    result = subprocess.run([str(exe), f'--mutable-template-ni{ni}'], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, (result.returncode, result.stderr)
    rows = result.stdout.splitlines()
    selected = [row for row in records if row['ni'] == ni]
    assert len(rows) == len(selected) == 16
    for native_index, (line, row) in enumerate(zip(rows, selected)):
        index, returned, payload = line.split()
        assert int(index) == native_index and int(returned) == row['destination']
        start = row['index'] * 736 + 192
        assert bytes.fromhex(payload) == data[start:start + 152]
prefix = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(private / 'mass-l2/boot-quarantine.tsv')], capture_output=True, text=True, timeout=30)
assert prefix.returncode == 7 and prefix.stdout == json.loads((private / 'mass-timebase/boot.json').read_text())['stdout']
live = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)], capture_output=True, text=True, timeout=30)
assert live.returncode == 7 and 'BOOT_BOUNDARY' in live.stdout and 'Mutable exception template execution' not in live.stdout
assert live.stdout == boot['stdout']
(output / 'live-replay.log').write_text(live.stdout + live.stderr)
report = {'result': 'SCOPED_RESET_STORE_NATIVE_COPY_ROLLBACK_STALE_GUARDS_VERIFIED_NEW_ENDPOINT_UNVERIFIED',
          'originalResetCases': 32, 'nativeCopyCases': 32, 'copiedBytes': 4864, 'refusalRollbackCases': 10, 'compiledStaleEntryRefusals': 38,
          'loweringSha256': sha(output / 'lowering.json'), 'bootSha256': sha(output / 'boot.json'),
          'oracleSha256': sha(measurement / 'comparison.json'), 'contractSourceSha256': sha(contract_source),
          'contractBaseSha256': sha(experiment / 'template_patch_contract.cpp'), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Scoped reset reuses existing patch cache contract after validating real reset caller; no new memory store.',
                     'Compositional synthetic fixture, not complete original OS vector/table/CPU-memory endpoint.',
                     'New guarded endpoint, handler relocation/dispatch, physical Wii timing and menu remain unverified.']}
(output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS scopedreset32original/32nativecopy/10rollback/38stale-entry checks; newbootendpoint unverified')
print(live.stdout[-1800:])

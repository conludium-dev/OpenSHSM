"""Compare real cache-backed template patching/copying and refuse compiled template execution."""
from pathlib import Path
import base64
import hashlib
import json
import struct
import subprocess
from template_patch_lowering import lower

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'mass-template-patch'
base = private / 'mass-fp64'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_template_modes_dolphin.py')], check=True)
metadata = json.loads((base / 'lowering.json').read_text())
lowering = json.loads((output / 'lowering.json').read_text())
assert lowering['baseLoweringSha256'] == sha(base / 'lowering.json')
for key, filename in [('adapterSha256', 'template_patch.h'), ('scriptSha256', 'build_template_patch.py'),
                      ('lowererSha256', 'template_patch_lowering.py'), ('baseBuilderSha256', 'build_branch.py'),
                      ('baseProbeSha256', 'template_copy_probe.h'), ('staleProbeSha256', 'template_stale_probe.h')]:
    assert lowering[key] == sha(experiment / filename)
assert lowering['seedHeaderSha256'] == sha(output / 'loader-bat-seed.h') == sha(base / 'loader-bat-seed.h')
assert lowering['fp64ProbeHeaderSha256'] == sha(output / 'fp64-template-probe.h') == sha(base / 'fp64-template-probe.h')
assert lowering['probeSha256'] == sha(output / 'mutable-template-probe.h')
probe = (experiment / 'template_copy_probe.h').read_text().replace('experiment_template_copy_probe', 'experiment_mutable_template_copy_probe')
probe = probe.replace('index * 256', '(index + (ni ? 16 : 0)) * 256')
probe = probe.replace('''        auto word = context.mmu.get_ptr(0x80211c08);
        for (unsigned byte = 0; byte < 4; ++byte) {
            word[byte] = value >> (24 - byte * 8);
        }''', '        experiment_template_patch(context, 0x80211c08, value, 0x802119a8);')
assert (output / 'mutable-template-probe.h').read_text() == '#include "template_patch.h"\n' + probe
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert len(metadata['records']) == len(lowering['records']) == 125
patches, guarded = [], set()
for old, record in zip(metadata['records'], lowering['records']):
    source = Path(old['directory']) / old['file']
    assert sha(source) == old['sourceSha256'] and old['file'] == record['file']
    expected, changes = lower(source.read_text(), original)
    target = Path(record['directory']) / record['file']
    assert target.read_text() == expected and record['changes'] == changes
    assert sha(target) == record['sourceSha256'] and sha(Path(str(target) + '.o')) == record['objectSha256']
    for change in changes:
        if change['kind'] == 'patch':
            patches.append(change)
        else:
            guarded.add(int(change['address'], 16))
assert len(patches) == 1 and guarded == set(range(0x80211ba0, 0x80211c38, 4))
header = struct.unpack('>64I', original[:256])
address = 0x80211ba0
section = next(index for index in range(7) if header[18 + index] <= address < header[18 + index] + header[36 + index])
offset = header[section] + address - header[18 + section]
template = original[offset:offset + 152]
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
contract = output / 'template-contract'
compile_result = subprocess.run(['clang++', '-std=c++20', '-O2', '-I', str(experiment), '-I', str(output),
                                 '-I', str(upstream / 'nWiiRuntime/include'), str(experiment / 'template_patch_contract.cpp'), '-o', str(contract)],
                                capture_output=True, text=True, timeout=30)
(output / 'contract-build.log').write_text(compile_result.stdout + compile_result.stderr)
assert compile_result.returncode == 0, compile_result.stderr
contract_result = subprocess.run([str(contract)], input=template.hex() + '\n', capture_output=True, text=True, timeout=30)
(output / 'contract-results.log').write_text(contract_result.stdout + contract_result.stderr)
assert contract_result.returncode == 0 and contract_result.stdout == 'TEMPLATE_CONTRACT writes=16 guards=10 entries=38\n', contract_result
boot = json.loads((output / 'boot.json').read_text())
exe = output / 'openshsm-mass-boot'
policy = private / 'mass-ni-guard/boot-quarantine.tsv'
assert boot['executableSha256'] == sha(exe) and boot['wrapperSha256'] == sha(output / 'boot-wrapper.cpp')
assert boot['loweringSha256'] == sha(output / 'lowering.json') and boot['policySha256'] == sha(policy)
stale = subprocess.run([str(exe), '--template-stale-check'], capture_output=True, text=True, timeout=30)
assert stale.returncode == 0 and stale.stdout == 'TEMPLATE_STALE_GUARDS 38\n', stale
measurement = private / 'dolphin-template-modes'
capture = json.loads((measurement / 'fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
data = base64.b64decode(capture['data'])
records = json.loads((measurement / 'generation.json').read_text())['records']
for ni in (0, 1):
    result = subprocess.run([str(exe), f'--mutable-template-ni{ni}'], capture_output=True, text=True, timeout=30)
    (output / f'original-template-ni{ni}.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, (result.returncode, result.stderr)
    rows, selected = result.stdout.splitlines(), [row for row in records if row['ni'] == ni]
    assert len(rows) == len(selected) == 16
    for native_index, (line, row) in enumerate(zip(rows, selected)):
        index, returned, payload = line.split()
        assert int(index) == native_index and int(returned) == row['destination']
        offset = row['index'] * 736 + 192
        assert bytes.fromhex(payload) == data[offset:offset + 152]
prefix = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(private / 'mass-l2/boot-quarantine.tsv')],
                        capture_output=True, text=True, timeout=30)
assert prefix.returncode == 7 and prefix.stdout == json.loads((private / 'mass-timebase/boot.json').read_text())['stdout']
live = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)],
                      capture_output=True, text=True, timeout=30)
(output / 'live-replay.log').write_text(live.stdout + live.stderr)
assert live.returncode == 7 and 'BOOT_BOUNDARY' in live.stdout
assert 'write instruction=802119a8 address=80211c08' not in live.stdout
report = {'result': 'SCOPED_TEMPLATE_PATCH_COPY_MATCH_STALE_COMPILED_EXECUTION_REFUSED_NEW_ENDPOINT_UNVERIFIED',
          'templateCases': 32, 'copiedBytes': 4864, 'refusalRollbackCases': 10,
          'guardedInstructionAddresses': 38, 'compiledStaleEntryRefusals': 38,
          'loweringSha256': sha(output / 'lowering.json'), 'bootSha256': sha(output / 'boot.json'),
          'executableSha256': sha(exe), 'oracleSha256': sha(measurement / 'comparison.json'),
          'contractSha256': sha(experiment / 'template_patch_contract.cpp'), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Measured single-word/value/CPU/cache/BAT profile only, on existing MMU/cache backing.',
                     'All emitted source-template instructions refuse execution, including mid-function entry; no original handler dispatch.',
                     'Old code-image validation and all other code-write guards remain strict.',
                     'Full new post-clock CPU/memory endpoint, additional template writes/vector relocation/menu/game unverified.']}
(output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS mutablepatch+originalmemcpy32cases/4864bytes;10rollbackguards/38compiledentryrefusals; fullendpoint pending')
print(live.stdout[-1400:], flush=True)

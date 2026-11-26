"""Verify whole-module BAT routing, original HID4 execution and shared backing/cache contract."""
from pathlib import Path
import base64
import hashlib
import json
import struct
import subprocess
from bat_lowering import lower

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/mass-bat')
base = Path('work/private-game/static-recomp/mass-performance')
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_bat_seed.py')], check=True)
subprocess.run(['python3', str(experiment / 'verify_hid4_dolphin.py')], check=True)
lowering = json.loads((output / 'lowering.json').read_text())
assert lowering['baseLoweringSha256'] == sha(base / 'lowering.json')
for key, filename in [('contextSha256', 'bat_context.h'), ('frontendSha256', 'bat_memory_frontend.h'),
                      ('resolverSha256', 'bat_translation.h'), ('probeSha256', 'bat_hid4_probe.h'),
                      ('rotateLowererSha256', 'rotate_record_lowering.py'),
                      ('lowererSha256', 'bat_lowering.py'), ('scriptSha256', 'build_bat.py'), ('baseBuilderSha256', 'build_branch.py')]:
    assert lowering[key] == sha(experiment / filename), filename
assert lowering['seedHeaderSha256'] == sha(output / 'loader-bat-seed.h')
assert lowering['seedProofSha256'] == sha(Path('work/private-game/static-recomp/dolphin-bat-seed/seed.json'))
assert lowering['memoryRoutingLines'] == 511904 and lowering['registerSites'] == 162
rotate_path = output / 'rotate-comparison.json'
rotate = json.loads(rotate_path.read_text())
assert rotate['result'] == 'ORIGINAL_ROTATE_RECORD_RESULT_XER_CR_ALIAS_MATCH'
assert rotate['loweringSha256'] == sha(output / 'lowering.json') and rotate['sites'] == lowering['rotateRecordSites']
assert rotate['verifierSha256'] == sha(experiment / 'verify_rotate_record.py')
assert rotate['generatedProbeSha256'] == sha(output / 'rotate-record-probe.cpp')
assert rotate['executableSha256'] == sha(output / 'rotate-record-probe')
metadata = json.loads((base / 'lowering.json').read_text())
assert len(metadata['records']) == len(lowering['records']) == 125
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
for original, record in zip(metadata['records'], lowering['records']):
    source = Path(original['directory']) / original['file']
    assert source.name == record['file'] and sha(source) == original['sourceSha256']
    updated, changes = lower(source.read_text(), dol)
    target = Path(record['directory']) / record['file']
    assert target.read_text() == updated and record['changes'] == changes
    assert sha(target) == record['sourceSha256'] and sha(Path(str(target) + '.o')) == record['objectSha256']
boot = json.loads((output / 'boot.json').read_text())
exe = output / 'openshsm-mass-boot'
assert boot['executableSha256'] == sha(exe) and boot['wrapperSha256'] == sha(output / 'boot-wrapper.cpp')
assert boot['loweringSha256'] == sha(output / 'lowering.json')
proof_path = Path('work/private-game/static-recomp/dolphin-hid4-probe/comparison.json')
proof = json.loads(proof_path.read_text())
generation = json.loads(Path('work/private-game/static-recomp/dolphin-hid4-probe/generation.json').read_text())
inputs, expected = [], []
for initial, observation in zip(generation['records'], proof['observations']):
    inputs.append([initial['cr'], initial['xer'], initial['ctr'], initial['expectedLr'], *initial['initialGpr']])
    expected.append([*observation['gpr'], observation['cr'], observation['lr'], observation['ctr'], observation['xer'], observation['msr'], observation['hid4'], observation['aliasValue']])
result = subprocess.run([str(exe), '--bat-hid4-check'], input=''.join(' '.join(map(str, row)) + '\n' for row in inputs), capture_output=True, text=True, timeout=30)
(output / 'hid4-native.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, (result.returncode, result.stderr)
assert [list(map(int, row.split())) for row in result.stdout.splitlines()] == expected
contract = output / 'bat-contract'
subprocess.run(['python3', str(experiment / 'build_bat_contract.py')], check=True)
contract_build = json.loads((output / 'contract-build.json').read_text())
assert contract_build['executableSha256'] == sha(contract)
assert contract_build['buildLogSha256'] == sha(output / 'contract-build.log')
result = subprocess.run([str(contract)], capture_output=True, text=True, timeout=30)
(output / 'contract.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and 'PASS guards=11' in result.stdout, (result.returncode, result.stdout, result.stderr)
coherence_path = Path('work/private-game/static-recomp/dolphin-coherence-probe/boot-true-dolphin.json')
coherence = json.loads(coherence_path.read_text(encoding='utf-8-sig'))
assert coherence['accurateCache'] == 'True'
gpr = struct.unpack_from('>32I', base64.b64decode(coherence['data']), 32)
samples = [int(value) for value in result.stdout.splitlines()[0].split()[1:]]
assert samples == list(gpr[5:10])
replay = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(base / 'boot-quarantine.tsv')], capture_output=True, text=True, timeout=30)
(output / 'boot-replay.log').write_text(replay.stdout + replay.stderr)
assert replay.returncode == 7 and 'BOOT_BOUNDARY pc=80210840 lr=802113e0 msr=2030' in replay.stdout
prefix = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', 'work/private-game/static-recomp/mass-l2/boot-quarantine.tsv'],
                        capture_output=True, text=True, timeout=30)
(output / 'pre-timebase-replay.log').write_text(prefix.stdout + prefix.stderr)
baseline_path = Path('work/private-game/static-recomp/mass-timebase/boot.json')
baseline = json.loads(baseline_path.read_text())
assert prefix.returncode == 7 and prefix.stdout == baseline['stdout'], 'BAT route changed the retained pre-timebase trace/state'
report = {'result': 'FULL_BAT_FRONTEND_ORIGINAL_HID4_AND_SHARED_CACHE_BOUNDED_PASS', 'originalHid4Cases': 8,
          'memoryRoutingLines': 511904, 'registerSites': 162, 'guardCases': 11,
          'loweringSha256': sha(output / 'lowering.json'), 'originalProofSha256': sha(proof_path), 'executableSha256': sha(exe),
          'contractSha256': sha(experiment / 'bat_contract.cpp'), 'contractExecutableSha256': sha(contract),
          'contractBuildSha256': sha(output / 'contract-build.json'),
          'retainedCoherenceCaptureSha256': sha(coherence_path), 'verifierSha256': sha(Path(__file__)),
          'rotateProofSha256': sha(rotate_path), 'rotateRecordSites': lowering['rotateRecordSites'],
          'preTimebaseBaselineSha256': sha(baseline_path),
          'limits': ['Original generated80-byte HID4 function from full module matches CPU/ABI/actual alias observations in the measured high-bit-set profile.',
                     'Shared cache samples match retained canonical-alias Dolphin observations; new cached BAT alias sequence is a native contract, not separately observed in Dolphin.',
                     'Loader BAT seed is a measured Dolphin fixture input; physical Wii startup/page tables/protection/L2-ST0 remain unverified.',
                     'HID4 live quarantine retained; full post-timebase CPU/memory endpoint and game/menu remain unverified.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS full BAT frontend:511904memory lines/162register sites; original HID48cases/shared cache/MEM1-MEM2/11guards; live gate retained')

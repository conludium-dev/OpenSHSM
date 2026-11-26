"""Verify shared clock routing and controlled reader without accepting live OS timing."""
from pathlib import Path
import hashlib
import json
import subprocess
from timebase_lowering import lower

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/mass-timebase')
base = Path('work/private-game/static-recomp/mass-carry')
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
lowering = json.loads((output / 'lowering.json').read_text())
assert lowering['baseLoweringSha256'] == sha(base / 'lowering.json')
assert lowering['scriptSha256'] == sha(experiment / 'build_timebase.py')
assert lowering['baseBuilderSha256'] == sha(experiment / 'build_branch.py')
assert lowering['lowererSha256'] == sha(experiment / 'timebase_lowering.py')
assert lowering['adapterSha256'] == sha(experiment / 'timebase_adapter.h')
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
count = 0
for record in lowering['records']:
    original = Path(record['inputDirectory']) / record['file']
    source = Path(record['directory']) / record['file']
    assert sha(original) == record['inputSha256'] and sha(source) == record['sourceSha256']
    assert sha(Path(str(source) + '.o')) == record['objectSha256']
    expected, changes = lower(original.read_text(), dol)
    assert source.read_text() == expected and record['changes'] == changes
    count += len(changes)
assert count == lowering['sites'] == 9 and len(lowering['records']) == 125
boot = json.loads((output / 'boot.json').read_text())
assert boot['result'] == 'TIMEBASE_QUARANTINE_RETAINED'
assert boot['executableSha256'] == sha(output / 'openshsm-mass-boot')
assert boot['loweringSha256'] == sha(output / 'lowering.json')
assert boot['wrapperSha256'] == sha(output / 'boot-wrapper.cpp')
policy = Path('work/private-game/static-recomp/mass-l2/boot-quarantine.tsv')
assert boot['policySha256'] == sha(policy)
previous = json.loads((base / 'boot.json').read_text())
assert boot['stdout'] == previous['stdout']
replay = subprocess.run([str(output / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol', str(policy)],
                        capture_output=True, text=True, timeout=30)
assert replay.returncode == 7 and replay.stdout == boot['stdout']
reader_path = output / 'reader-comparison.json'
reader = json.loads(reader_path.read_text())
assert reader['result'] == 'ORIGINAL_TIMEBASE_RETRY_CONSUMER_CONTROLLED_MATCH' and reader['cases'] == 75
assert reader['executableSha256'] == sha(output / 'openshsm-mass-boot')
assert reader['verifierSha256'] == sha(experiment / 'verify_timebase_reader.py')
assert reader['loweringSha256'] == sha(output / 'lowering.json')
exe = output / 'timebase-contract'
result = subprocess.run(['clang++', '-std=c++20', '-O0', '-include', 'bit', '-I', str(upstream / 'nWiiRuntime/include'),
                         str(experiment / 'timebase_contract.cpp'), str(experiment / 'processor_adapter.cpp'), '-o', str(exe)],
                        capture_output=True, text=True, timeout=30)
assert result.returncode == 0, result.stderr
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
assert result.returncode == 0 and 'TIMEBASE_CONTRACT conversion monotonic1000 guards3 PASS' in result.stdout
report = {'result': 'CONTROLLED_TIMEBASE_READER_AND_PROVIDER_BOUNDED_PASS', 'sites': count, 'readerCases': 75,
          'quarantineRetained': True, 'preTimebaseBootUnchanged': True,
          'readerSha256': sha(reader_path), 'contractSourceSha256': sha(experiment / 'timebase_contract.cpp'),
          'contractExeSha256': sha(exe), 'probeSourceSha256': sha(experiment / 'timebase_probe.h'), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Controlled TBL/TBU fixture proves original consumer retry/return behavior, not hardware timebase instruction timing.',
                     'PC monotonic elapsed clock starts at zero; RTC epoch/calendar and live whole-OS clock consumers unverified.',
                     'Timebase quarantine retained; DEC read/write/delivery remain separate unsupported paths.']}
(output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('BOUNDED PASS:9clock sites/75controlled original reader cases/provider guards/pre-timebase baseline; live boot pending')

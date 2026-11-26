"""Module-wide immediate carry scope and strict normalized original OS-prefix comparison."""
from pathlib import Path
import base64
import hashlib
import json
import re
import struct
import subprocess
from carry_lowering import lower

experiment = Path('experiments/wii-static-recomp')
native = Path('work/private-game/static-recomp/mass-carry')
output = Path('work/private-game/static-recomp/dolphin-poll-normalized-probe')
base = Path('work/private-game/static-recomp/mass-branch')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
lowering = json.loads((native / 'lowering.json').read_text())
assert lowering['baseLoweringSha256'] == sha(base / 'lowering.json')
assert lowering['scriptSha256'] == sha(experiment / 'build_carry.py')
assert lowering['baseBuilderSha256'] == sha(experiment / 'build_branch.py')
assert lowering['lowererSha256'] == sha(experiment / 'carry_lowering.py')
assert lowering['adapterSha256'] == sha(experiment / 'carry_adapter.h')
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
count = 0
for record in lowering['records']:
    original = Path(record['inputDirectory']) / record['file']
    source = Path(record['directory']) / record['file']
    assert sha(original) == record['inputSha256'] and sha(source) == record['sourceSha256']
    assert sha(Path(str(source) + '.o')) == record['objectSha256']
    expected, changes = lower(original.read_text(), dol)
    assert source.read_text() == expected and changes == record['changes']
    count += len(changes)
assert count == lowering['sites'] == 2088 and len(lowering['records']) == 125
isa_path = native / 'isa-comparison.json'
isa = json.loads(isa_path.read_text())
assert isa['result'] == 'ORIGINAL_IMMEDIATE_CARRY_RESULT_XER_CR_ALIAS_MATCH'
assert isa['loweringSha256'] == sha(native / 'lowering.json') and isa['adapterSha256'] == sha(experiment / 'carry_adapter.h')
assert isa['verifierSha256'] == sha(experiment / 'verify_carry_isa.py')
assert isa['sourceSha256'] == sha(experiment / 'carry_probe.cpp') and isa['executableSha256'] == sha(native / 'carry-probe')
boot = json.loads((native / 'boot.json').read_text())
assert boot['loweringSha256'] == sha(native / 'lowering.json') and boot['executableSha256'] == sha(native / 'openshsm-mass-boot')
assert boot['wrapperSha256'] == sha(Path('work/private-game/static-recomp/mass-poll/boot-wrapper.cpp'))
policy = Path('work/private-game/static-recomp/mass-l2/boot-quarantine.tsv')
assert boot['policySha256'] == sha(policy)
replay = subprocess.run([str(native / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol', str(policy)],
                        capture_output=True, text=True, timeout=30)
assert replay.returncode == 7 and replay.stdout == boot['stdout']
assert 'BOOT_POLL checks=26830' in boot['stdout']
comparator = experiment / 'verify_dcache.py'
body = comparator.read_text().split("generation = json.loads((output / 'generation.json').read_text())", 1)[1]
body = "generation = json.loads((output / 'generation.json').read_text())" + body
body = body.replace('build_dcache_probe.py', 'build_poll_normalized_probe.py').replace('run_dcache_probe.ps1', 'run_poll_normalized_probe.ps1')
body = body.replace('802106c0', '8021c000').replace('802134d8', '8021c054')
body = body.replace('UNVERIFIED_PROCESSOR_REGISTER_1017', 'UNVERIFIED_PROCESSOR_REGISTER_269')
body = body.replace('(0x8021c054, 0, 0, 0xa0000000, 0xc000, 0x2030)', '(0x8021c054, 0, 0x20000000, 0xa0000000, 0xc000, 0x2030)')
body = body.replace("'DCE_ENABLE_BOOT_PREFIX_VERIFIED'", "'IMMEDIATE_CARRY_NORMALIZED_OS_PREFIX_VERIFIED'")
body = body.replace("'0x802106C0 before L2CR read'", "'0x8021C000 before OS timebase read'")
body = body.replace("(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\\n')", '')
body = body.replace("print('PASS scoped native DCE/original accurate-cache boot endpoint; next L2CR1017; 3accepts/8refusals')", '')
exec(compile(body, str(comparator), 'exec'), globals())
assert [ctr, xer] == state[74:76] and state[75] == 0x20000000
assert generation['normalizedInputs'] == [{'address': '0x80000034', 'value': 0}, {'address': '0x800000f4', 'value': 0}]
assert generation['baseMeasurementSha256'] == sha(Path('work/private-game/static-recomp/dolphin-poll-probe/boot.dol'))
assert generation['baseGenerationSha256'] == sha(Path('work/private-game/static-recomp/dolphin-poll-probe/generation.json'))
assert struct.unpack_from('>I', data, 24)[0] == 0x80000000
report['comparisonSourceSha256'] = sha(comparator)
report['isaComparisonSha256'] = sha(isa_path)
report['adapterSha256'] = sha(experiment / 'carry_adapter.h')
report['moduleSites'] = count
report['limits'] = ['subfic/addic/addic. result/carry correction only; other PPC arithmetic and complete CFG semantics remain unverified.',
                    'Controlled normalized low-memory startup fixture, not physical Wii/retail power-on.',
                    'CPU/FP/stack snapshot does not verify every initialized data/BSS byte or the full OS initializer.',
                    'Timebase remains quarantined; timer progression/event delivery/resume/OS/IOS/GX/menu/game remain unverified.']
(native / 'boot-comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'PASS2088immediate-carry sites/{isa["cases"]}original PPC cases/strict normalized OS CPU endpoint; next timebase')

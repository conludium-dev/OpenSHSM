"""Module-wide scope audit and accurate-cache original __init_data endpoint."""
from pathlib import Path
import base64
import hashlib
import json
import re
import struct
import subprocess
from branch_lowering import lower

experiment = Path('experiments/wii-static-recomp')
native = Path('work/private-game/static-recomp/mass-branch')
output = Path('work/private-game/static-recomp/dolphin-branch-probe')
base = Path('work/private-game/static-recomp/mass-l2')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
lowering = json.loads((native / 'lowering.json').read_text())
assert lowering['baseLoweringSha256'] == sha(base / 'lowering.json')
assert lowering['scriptSha256'] == sha(experiment / 'build_branch.py')
assert lowering['lowererSha256'] == sha(experiment / 'branch_lowering.py')
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
assert count == lowering['sites'] == 13215 and len(lowering['records']) == 125
isa_path = native / 'isa-comparison.json'
isa = json.loads(isa_path.read_text())
assert isa['result'] == 'ORIGINAL_BC_ORACLE_AND_CALLBACK_PATH_MATCH'
assert isa['loweringSha256'] == sha(native / 'lowering.json')
assert isa['verifierSha256'] == sha(experiment / 'verify_branch_isa.py')
assert isa['sourceSha256'] == sha(native / 'branch-predicate-probe.cpp')
assert isa['executableSha256'] == sha(native / 'branch-predicate-probe')
assert (isa['classes'], isa['cases']) == (13, 624)
boot = json.loads((native / 'boot.json').read_text())
assert boot['executableSha256'] == sha(native / 'openshsm-mass-boot')
assert boot['loweringSha256'] == sha(native / 'lowering.json')
assert boot['wrapperSha256'] == sha(base / 'boot-wrapper.cpp')
policy = base / 'boot-quarantine.tsv'
assert boot['policySha256'] == sha(policy)
replay = subprocess.run([str(native / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol', str(policy)],
                        capture_output=True, text=True, timeout=30)
assert replay.returncode == 7 and replay.stdout == boot['stdout']
comparator = experiment / 'verify_dcache.py'
body = comparator.read_text().split("generation = json.loads((output / 'generation.json').read_text())", 1)[1]
body = "generation = json.loads((output / 'generation.json').read_text())" + body
body = body.replace('build_dcache_probe.py', 'build_branch_probe.py').replace('run_dcache_probe.ps1', 'run_branch_probe.ps1')
body = body.replace('802106c0', '8000656c').replace('802134d8', '8000632c')
body = body.replace('UNVERIFIED_PROCESSOR_REGISTER_1017', 'Scheduler callback service unavailable')
body = body.replace("'DCE_ENABLE_BOOT_PREFIX_VERIFIED'", "'CONDITIONAL_BACKEDGE_BOOT_PREFIX_VERIFIED'")
body = body.replace("'0x802106C0 before L2CR read'", "'0x8000656C before taken unconditional __init_data backedge'")
body = body.replace("(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\\n')", '')
body = body.replace("print('PASS scoped native DCE/original accurate-cache boot endpoint; next L2CR1017; 3accepts/8refusals')", '')
exec(compile(body, str(comparator), 'exec'), globals())
assert generation['baseGeneratorSha256'] == sha(experiment / 'build_dcache_probe.py')
assert generation['l2GeneratorSha256'] == sha(experiment / 'build_l2_probe.py')
assert struct.unpack_from('>I', data, 24)[0] == 0x80000000
report['comparisonSourceSha256'] = sha(comparator)
report['isaComparisonSha256'] = sha(isa_path)
report['moduleSites'] = count
report['limits'] = ['Conditional backedge polling is a PC adaptation; actual scheduler/interrupt delivery/resume remains unavailable.',
                    'ISA comparison tests extracted templates, not full CFG equivalence or arbitrary generated game function semantics.',
                    'L2 register model follows Dolphin; physical L2 effects/BAT/DMA/locked-cache/quantized paired/OS/IOS/GX/menu unverified.',
                    'Controlled accurate-cache boot fixture, not physical Wii or unmodified retail startup.']
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS module-wide13215backedges/13classes/624PPCcases/accurate-cache boot; next taken __init_data scheduler boundary')

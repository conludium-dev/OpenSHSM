"""Reuse established CPU endpoint comparison with explicit L2 scope/provenance checks."""
from pathlib import Path
import base64
import hashlib
import json
import re
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
native = Path('work/private-game/static-recomp/mass-l2')
output = Path('work/private-game/static-recomp/dolphin-l2-probe')
base = Path('work/private-game/static-recomp/mass-dcache')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
lowering = json.loads((native / 'lowering.json').read_text())
assert lowering['baseLoweringSha256'] == sha(base / 'lowering.json')
assert lowering['adapterSha256'] == sha(experiment / 'l2_adapter.h')
assert lowering['scriptSha256'] == sha(experiment / 'build_l2.py')
assert lowering['wrapperSha256'] == sha(native / 'boot-wrapper.cpp')
prior = {record['file']: record for record in json.loads((base / 'lowering.json').read_text())['records']}
changes = {}
for change in lowering['changes']:
    changes.setdefault(change['file'], {})[change['line'] - 1] = change
assert len(lowering['changes']) == 4
for record in lowering['records']:
    source = Path(record['directory']) / record['file']
    assert sha(source) == record['sourceSha256'] and sha(Path(str(source) + '.o')) == record['objectSha256']
    before_source = Path(prior[record['file']]['directory']) / record['file']
    assert sha(before_source) == prior[record['file']]['sourceSha256']
    before, after = before_source.read_text().splitlines(True), source.read_text().splitlines(True)
    assert len(before) == len(after)
    for index, (old, new) in enumerate(zip(before, after)):
        if index in changes.get(record['file'], {}):
            change = changes[record['file']][index]
            assert (old, new) == (change['before'], change['after'])
        else:
            assert old == new
boot = json.loads((native / 'boot.json').read_text())
assert boot['executableSha256'] == sha(native / 'openshsm-mass-boot')
assert boot['loweringSha256'] == sha(native / 'lowering.json')
policy = native / 'boot-quarantine.tsv'
assert boot['policySha256'] == sha(policy)
prior_policy = Path('work/private-game/static-recomp/mass-icache/boot-quarantine.tsv').read_text().splitlines(True)
assert policy.read_text() == ''.join(line for line in prior_policy if line not in lowering['removedPolicyEntries'])
replay = subprocess.run([str(native / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol', str(policy)],
                        capture_output=True, text=True, timeout=30)
assert replay.returncode == 7 and replay.stdout == boot['stdout']
comparator = experiment / 'verify_dcache.py'
body = comparator.read_text().split("generation = json.loads((output / 'generation.json').read_text())", 1)[1]
body = "generation = json.loads((output / 'generation.json').read_text())" + body
body = body.replace('build_dcache_probe.py', 'build_l2_probe.py').replace('run_dcache_probe.ps1', 'run_l2_probe.ps1')
body = body.replace('802106c0', '80213534').replace('802134d8', '80213530')
body = body.replace('lr=80213530 msr=2030', 'lr=80213530 msr=30')
body = body.replace('UNVERIFIED_PROCESSOR_REGISTER_1017', 'Scheduler callback service unavailable')
body = body.replace('(0x80213530, 0, 0, 0xa0000000, 0xc000, 0x2030)', '(0x80213530, 0, 0, 0xa0000000, 0xc000, 0x30)')
body = body.replace("'DCE_ENABLE_BOOT_PREFIX_VERIFIED'", "'L2_REGISTER_BOOT_PREFIX_VERIFIED'")
body = body.replace("'0x802106C0 before L2CR read'", "'0x80213534 before L2 polling branch'")
body = body.replace("print('PASS scoped native DCE/original accurate-cache boot endpoint; next L2CR1017; 3accepts/8refusals')", '')
body = body.replace("(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\\n')", '')
exec(compile(body, str(comparator), 'exec'), globals())
assert generation['baseGeneratorSha256'] == sha(experiment / 'build_dcache_probe.py')
assert struct.unpack_from('>I', data, 24)[0] == gpr[3] == 0x200000
assert state[2] == 2, 'CR0 must represent not-taken bne at this endpoint'
exe = native / 'l2-contract'
result = subprocess.run(['clang++', '-std=c++20', '-O0', '-include', 'bit', '-I', str(upstream / 'nWiiRuntime/include'),
                         str(experiment / 'l2_contract.cpp'), str(experiment / 'processor_adapter.cpp'), '-o', str(exe)],
                        capture_output=True, text=True, timeout=30)
assert result.returncode == 0, result.stderr
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
assert result.returncode == 0 and 'L2_REFERENCE_CONTRACT 8roundtrips 2privilege refusals PASS' in result.stdout
report['referenceContractSourceSha256'] = sha(experiment / 'l2_contract.cpp')
report['referenceContractExeSha256'] = sha(exe)
report['comparisonSourceSha256'] = sha(comparator)
report['l2Readback'] = '0x00200000'
report['originalBranchTaken'] = False
report['limits'] = ['Stored L2CR reference model follows Dolphin; physical L2 cache/invalidation completion/coherence/timing unverified.',
                    'Original CPU boot through L2 register writes matches an accurate-cache controlled fixture before polling branch.',
                    'Emitter calls scheduler before checking conditional branch; this endpoint refusal is not evidence of an original scheduler request.',
                    'No physical Wii/retail boot, full BAT/locks/DMA/OS/IOS/GX/menu/game acceptance.']
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS bounded L2 register/original boot endpoint; next investigate emitter scheduler call on not-taken bne')

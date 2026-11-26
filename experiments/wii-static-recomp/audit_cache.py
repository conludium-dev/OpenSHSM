"""Verify incremental cache stage and preserve the earlier whole-module/processor evidence."""
from pathlib import Path
import hashlib
import json
import subprocess

base = Path('work/private-game/static-recomp/mass-current')
output = Path('work/private-game/static-recomp/mass-cache')
experiment = Path('experiments/wii-static-recomp')
lowering = json.loads((output / 'lowering.json').read_text())
boot = json.loads((output / 'boot.json').read_text())
cache = json.loads((output / 'cache-check.json').read_text())
comparison = json.loads((output / 'boot-original-comparison.json').read_text())
assert lowering['result'] == cache['result'] == comparison['result'] == 'PASS'
assert len(lowering['changes']) == 27 and len(lowering['files']) == 2
assert sum(change['spr'] == 920 for change in lowering['changes']) == 14
assert sum(change['spr'] == 1008 for change in lowering['changes']) == 13
for key, path in [('adapterHeaderSha256', experiment / 'processor_adapter.h'),
                  ('adapterSourceSha256', experiment / 'processor_adapter.cpp'), ('loweringScriptSha256', experiment / 'lower_processor.py')]:
    assert lowering[key] == hashlib.sha256(path.read_bytes()).hexdigest(), key
assert lowering['baseGenerationSha256'] == hashlib.sha256((base / 'generation.json').read_bytes()).hexdigest()
for record in lowering['files']:
    assert record['baseSha256'] == hashlib.sha256((base / record['file']).read_bytes()).hexdigest()
    assert record['sourceSha256'] == hashlib.sha256((output / record['file']).read_bytes()).hexdigest()
    assert record['objectSha256'] == hashlib.sha256((output / (record['file'] + '.o')).read_bytes()).hexdigest()
    old = (base / record['file']).read_text().splitlines()
    new = (output / record['file']).read_text().splitlines()
    assert len(old) == len(new)
    modifications = [change for change in lowering['changes'] if change['file'] == record['file']]
    assert sum(before != after for before, after in zip(old, new)) == len(modifications)
    assert all(any(change['priorLowering'] == before.strip() and change['adapterLowering'] == after.strip() for change in modifications)
               for before, after in zip(old, new) if before != after)
exe_hash = hashlib.sha256((output / 'openshsm-mass-boot').read_bytes()).hexdigest()
assert boot['executableSha256'] == cache['executableSha256'] == exe_hash
assert boot['wrapperSha256'] == cache['wrapperSha256'] == hashlib.sha256((experiment / 'mass_boot.cpp').read_bytes()).hexdigest()
assert boot['policySha256'] == hashlib.sha256((output / 'boot-quarantine.tsv').read_bytes()).hexdigest()
assert comparison['bootReportSha256'] == hashlib.sha256((output / 'boot.json').read_bytes()).hexdigest()
assert comparison['originalInstructionsExecuted'] == 73 and comparison['boundary'] == '0x80210890'
assert comparison['cacheInvalidations'] == 1 and comparison['registersLrMsrPcStackMatch']
assert cache['cases'] == 5
subprocess.run(['python3', str(experiment / 'audit_processor.py')], check=True)
report = {'result': 'PASS', 'scope': 'HID0 immutable-code instruction-cache adapter and original bootstrap prefix; full game not reached.',
          'overriddenProcessorSites': 27, 'hid0Sites': 13, 'recompiledBatches': 2, 'cacheContractCases': 5,
          'originalBootstrapInstructions': 73, 'previousInstructions': 54, 'nextBoundary': '0x80210890/FPR-FPSCR initialization',
          'releaseUnchanged': True, 'limits': cache['limits'] + comparison['limits'],
          'next': 'Implement and independently verify FPSCR/mtfsf plus original FPR/paired-single initialization, then continue cache-control/OS bootstrap.'}
(output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS:cache contract/27sites/73original boot instructions; FPR/FPSCR and broader cache effects remain open')

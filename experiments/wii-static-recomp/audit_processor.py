"""Audit incremental processor lowering, register policy and original bootstrap without widening acceptance."""
from pathlib import Path
import hashlib
import json
import re
import struct
import subprocess

base = Path('work/private-game/static-recomp/mass-current')
output = Path('work/private-game/static-recomp/mass-processor')
experiment = Path('experiments/wii-static-recomp')
lowering = json.loads((output / 'lowering.json').read_text())
boot = json.loads((output / 'boot.json').read_text())
registers = json.loads((output / 'register-check.json').read_text())
comparison = json.loads((output / 'boot-original-comparison.json').read_text())
assert lowering['result'] == registers['result'] == comparison['result'] == 'PASS'
assert len(lowering['changes']) == 14 and len(lowering['files']) == 2
for key, path in [('adapterHeaderSha256', experiment / 'processor_adapter.h'),
                  ('adapterSourceSha256', experiment / 'processor_adapter.cpp'), ('loweringScriptSha256', experiment / 'lower_processor.py')]:
    assert lowering[key] == hashlib.sha256(path.read_bytes()).hexdigest(), key
assert lowering['baseGenerationSha256'] == hashlib.sha256((base / 'generation.json').read_bytes()).hexdigest()
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
header = struct.unpack('>64I', dol[:256])
changed_count = 0
for record in lowering['files']:
    original = base / record['file']
    target = output / record['file']
    assert record['baseSha256'] == hashlib.sha256(original.read_bytes()).hexdigest()
    assert record['sourceSha256'] == hashlib.sha256(target.read_bytes()).hexdigest()
    assert record['objectSha256'] == hashlib.sha256((output / (record['file'] + '.o')).read_bytes()).hexdigest()
    prior = original.read_text().splitlines()
    current = target.read_text().splitlines()
    assert len(prior) == len(current)
    for index, (before, after) in enumerate(zip(prior, current)):
        if before == after:
            continue
        match = re.search(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', prior[index - 1])
        assert match, (record['file'], index)
        address, opcode = [int(value, 16) for value in match.groups()]
        spr = ((opcode >> 16) & 31) | (((opcode >> 11) & 31) << 5)
        assert opcode >> 26 == 31 and ((opcode >> 1) & 1023) in (339, 467) and spr == 920
        section = next(section for section in range(18) if header[18 + section] <= address < header[18 + section] + header[36 + section])
        assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == opcode
        changes = [change for change in lowering['changes'] if change['file'] == record['file'] and int(change['address'], 16) == address
                   and change['priorLowering'] == before.strip() and change['adapterLowering'] == after.strip()]
        assert changes
        changed_count += 1
assert changed_count == 14
exe_hash = hashlib.sha256((output / 'openshsm-mass-boot').read_bytes()).hexdigest()
assert boot['executableSha256'] == registers['executableSha256'] == exe_hash
assert boot['wrapperSha256'] == hashlib.sha256((experiment / 'mass_boot.cpp').read_bytes()).hexdigest()
assert boot['policySha256'] == hashlib.sha256((output / 'boot-quarantine.tsv').read_bytes()).hexdigest()
assert boot['objectReportSha256'] == hashlib.sha256((base / 'objects.json').read_bytes()).hexdigest()
assert registers['scriptSha256'] == hashlib.sha256((experiment / 'verify_processor.py').read_bytes()).hexdigest()
assert registers['policyAndGuardCases'] == len(registers['records']) == 576
assert registers['originalPpcLegalWriteReadCases'] == 256 and registers['invalidInputGuards'] == 6
assert comparison['bootReportSha256'] == hashlib.sha256((output / 'boot.json').read_bytes()).hexdigest()
assert comparison['originalInstructionsExecuted'] == 54 and comparison['boundary'] == '0x802130D0'
assert comparison['hid2OriginalReadback'] == 0xa0000000 and comparison['registersLrMsrPcStackMatch']
subprocess.run(['python3', str(experiment / 'audit_mass.py')], check=True)
report = {'result': 'PASS', 'scope': 'Incremental HID2 register adapter and verified original bootstrap advancement; original menu/game not reached.',
          'loweredHid2Sites': 14, 'recompiledBatches': 2, 'unchangedBaseObjectsReused': 123,
          'policyAndGuardCases': 576, 'originalPpcLegalWriteReadCases': 256, 'invalidInputGuards': 6,
          'originalBootstrapInstructions': 54, 'previousBootstrapInstructions': 47,
          'nextBootBoundary': '0x802130D0', 'nextRegister': 'HID0/SPR1008',
          'releaseUnchanged': True, 'limits': registers['limits'] + comparison['limits'],
          'next': 'Verify HID0 cache-control/ICFlashInvalidate semantics before extending hardware/FPR/cache/OS bootstrap.'}
(output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS:incremental HID2/14sites/2batches/576policy/256original/6guards/54boot instructions; HID0 remains open')

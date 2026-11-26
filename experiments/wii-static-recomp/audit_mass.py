"""Audit generation/object/link/boot-prefix evidence while preserving broad unverified-game scope."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess

output = Path('work/private-game/static-recomp/mass-current')
generation = json.loads((output / 'generation.json').read_text())
syntax = json.loads((output / 'compilation.json').read_text())
objects = json.loads((output / 'objects.json').read_text())
boot = json.loads((output / 'boot.json').read_text())
comparison = json.loads((output / 'boot-original-comparison.json').read_text())
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
assert generation['dolSha256'] == hashlib.sha256(dol).hexdigest()
assert generation['result'] == 'PASS' and generation['candidateFunctions'] == 17873
assert generation['driverSha256'] == hashlib.sha256(Path('experiments/wii-static-recomp/nwii_mass_driver.cpp').read_bytes()).hexdigest()
for path, digest in generation['backendSourcesSha256'].items():
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest, path
for name, digest in generation['generatedSha256'].items():
    assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest, name
assert len(generation['generatedSha256']) == generation['generatedFiles'] == 125
assert len(generation['rejectedAutomaticHle']) == 5
for report in (syntax, objects):
    assert report['result'] == 'PASS' and report['failedFiles'] == 0 and report['filesChecked'] == 125
    assert report['generationReportSha256'] == hashlib.sha256((output / 'generation.json').read_bytes()).hexdigest()
    for record in report['records']:
        assert record['exitCode'] == 0 and record['sourceSha256'] == generation['generatedSha256'][record['file']]
        if 'objectSha256' in record:
            assert hashlib.sha256((output / (record['file'] + '.o')).read_bytes()).hexdigest() == record['objectSha256']
words = struct.unpack('>64I', dol[:256])
unique = set()
count = 0
with (output / 'instructions.tsv').open() as stream:
    for line in stream:
        entry, address, opcode = [int(value, 16) for value in line.split()]
        index = next(index for index in range(18) if words[18 + index] <= address < words[18 + index] + words[36 + index])
        assert struct.unpack_from('>I', dol, words[index] + address - words[18 + index])[0] == opcode
        unique.add(address)
        count += 1
assert boot['result'] == 'BLOCKED_AT_ORIGINAL_BOOT' and comparison['result'] == 'PASS'
assert boot['executableSha256'] == hashlib.sha256((output / 'openshsm-mass-boot').read_bytes()).hexdigest()
assert boot['wrapperSha256'] == hashlib.sha256(Path('experiments/wii-static-recomp/mass_boot.cpp').read_bytes()).hexdigest()
assert boot['objectReportSha256'] == hashlib.sha256((output / 'objects.json').read_bytes()).hexdigest()
assert boot['policySha256'] == hashlib.sha256((output / 'boot-quarantine.tsv').read_bytes()).hexdigest()
assert comparison['bootReportSha256'] == hashlib.sha256((output / 'boot.json').read_bytes()).hexdigest()
assert comparison['registersLrMsrPcStackMatch'] and comparison['boundary'] == '0x802107D0'
subprocess.run(['python3', 'experiments/wii-static-recomp/audit_phone_fragment.py'], check=True)
report = {'result': 'PASS', 'scope': 'Whole candidate-set generation/native object compilation/link plus verified original bootstrap prefix; game boot not achieved.',
          'candidateFunctions': 17873, 'cppFiles': 125, 'generationBytes': generation['generatedBytes'],
          'irOpcodeRecordsVerifiedAgainstDol': count, 'uniqueDolAddressesInIr': len(unique),
          'nativeObjects': 125, 'nativeLinkPassed': True, 'rejectedAutomaticHleLabels': 5,
          'emitterMarkers': syntax['generatedMarkers'], 'quarantinedFunctions': boot['quarantinedFunctions'],
          'originalBootstrapInstructionsMatched': comparison['originalInstructionsExecuted'],
          'firstBootBoundary': comparison['boundary'], 'firstProcessorRegister': 'HID2/SPR920',
          'releaseUnchanged': True, 'limits': generation['limits'] + comparison['limits'],
          'next': 'Verify explicit HID2/Gekko processor-register adapter, then continue original hardware/cache/OS bootstrap toward original menu/scene; do not replace consumers with success stubs.'}
(output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS:mass generation/native objects/link/original boot-prefix audit;', count, 'DOL opcode records; original menu/game remains unverified')

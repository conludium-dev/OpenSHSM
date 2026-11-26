"""Verify actual external-vector delivery, original SI callback and rfi return."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'verify_si_irq_dolphin.py'
body = parent.read_text().replace('dolphin-si-irq', 'dolphin-si-vector')
body = body.replace('build_si_irq_dolphin.py', 'build_si_vector_dolphin.py').replace('run_si_irq_dolphin.ps1', 'run_si_vector_dolphin.ps1')
marker = 'values = []'
assert body.count(marker) == 1
body = body.replace(marker, '''assert generation['irqGeneratorSha256'] == sha(experiment / 'build_si_irq_dolphin.py')
vector_section = offset(0x80211ba0, original_header)
expected_vector = list(struct.unpack_from('>38I', original, vector_section))
assert expected_vector[26] == 0x38600000
expected_vector[26] = 0x38600004
assert generation['vectorWords'] == expected_vector
assert list(struct.unpack('>38I', base64.b64decode(capture['vectorCode']))) == expected_vector
main_start = offset(0x80600000, header)
main_end = offset(min(patch['trampoline'] for patch in generation['patches']), header)
main_words = struct.unpack('>' + 'I' * ((main_end - main_start) // 4), image[main_start:main_end])
calls = []
for index, word in enumerate(main_words):
    if word >> 26 == 18 and word & 3 == 1:
        displacement = word & 0x03fffffc
        if displacement & 0x02000000:
            displacement -= 0x04000000
        calls.append(0x80600000 + index * 4 + displacement)
assert calls == [0x8020fd00] * 16
vector_values = []
''' + marker)
marker = '    actual = list(struct.unpack_from(\'>22I\', row, 24))'
assert body.count(marker) == 1
body = body.replace(marker, '''    vector = list(struct.unpack_from('>12I', row, 112))
    entry = generation['vectorRecords'][index]
    assert entry['wait'] == entry['enable'] + 4
    assert entry['waitEnd'] == entry['wait'] + 12
    assert struct.unpack_from('>I', image, offset(entry['enable'], header))[0] == 0x7c000124
    assert vector == [0xa032, entry['wait'], 0xa032, 0x80540000, 0x805335e0, 0x8052e720,
        0xc0680000 + index * 736, 0, 0, 0, entry['wait'], 20], (index, vector)
    vector_values.append({'index': index, 'observations': vector})
''' + marker)
body = body.replace('ORIGINAL_SI_IRQ_HANDLER16_CALLBACK_PI_STATUS_VALIDATED', 'ORIGINAL_SI_CPU_VECTOR16_CALLBACK_RETURN_VALIDATED')
body = body.replace('Not unpatched control or automatic CPU exception delivery; completion timing/all registers/active device input remain unverified.',
    'Automatic delivery verified only on the prepared vector/context/None-port fixture; unpatched retail startup, timing/all registers/active input remain unverified.')
body = body.replace("'captureSha256': sha(capture_path)", "'vectorValues': vector_values, 'captureSha256': sha(capture_path)")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/dolphin-si-vector')
path = output / 'comparison.json'
report = json.loads(path.read_text())
report['baseVerifierSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report['ghidraEvidence'] = {}
for directory in ('ios-exception-vector', 'ios-irq-dispatch'):
    evidence = Path('work/private-game/static-recomp') / directory / 'ghidra/verification.json'
    ghidra = json.loads(evidence.read_text())
    for row in ghidra['records']:
        assert row['objectSha256'] == sha(Path('work/private-game/static-recomp/dtk-output/obj/auto_03_802045CC_text.o'))
        assert row['assemblySha256'] == sha(evidence.parent / (row['name'] + '.asm'))
        assert row['decompiledSha256'] == sha(evidence.parent / (row['name'] + '.c'))
    report['ghidraEvidence'][directory] = sha(evidence)
report['originalBehavior'] = ['Capture: pending PI cause8 with mask8 and EE/RI enters the installed external vector; IRQ20 acknowledges SI and callback returns error8.',
    'Capture: context SRR0 equals the first instruction after enabling EE, SRR1 and returned MSR are A032, saved SP/r2/r13/r30 match the interrupted fixture.',
    'Own-DOL/Ghidra: vector152bytes, ExternalInterruptHandler80bytes and dispatcher680bytes implement context save/handler selection/OSLoadContext return.']
report['inferredBehavior'] = ['Retail boot must install compatible context/table/mask/scheduler state before this delivery path can run; current native boot has not demonstrated it.']
report['pcAdaptation'] = ['Private harness installs the vector with exception ID4, sets context/table/software masks/scheduler hint0 and enables EE after hardware completion.',
    'Three existing observers replay displaced instructions; Dolphin interpreter with AccurateCPUCache and four None ports supplies the original-code oracle.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS16 CPU SI external exceptions: copied original vector/IRQ20/context SRR/EE restoration/rfi return')

"""Verify original cache flush, real syscall return and cached/physical visibility."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-flush-syscall')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
capture = json.loads((output / 'fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
for key, name in [('generatorSha256', 'build_flush_syscall_dolphin.py'), ('parentGeneratorSha256', 'build_si_query_dolphin.py'),
        ('helperSha256', 'build_dolphin_probe.py'), ('baseRunnerSha256', 'run_dolphin_probe.ps1'), ('wrapperSha256', 'run_flush_syscall_dolphin.ps1')]:
    assert generation[key] == sha(experiment / name)
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
original = original_path.read_bytes()
image = (output / 'fpr-init.dol').read_bytes()
assert generation['originalSha256'] == sha(original_path)
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256']
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
assert generation['patches'] == [] and image[256:len(original)] == original[256:]
assert capture['accurateCache'] == 'True' and capture['records'] == len(generation['records']) == 16
for flag in ('Dolphin.Core.CPUCore=0', '-v Null', 'dolphin-flush-syscall-user'):
    assert flag in capture['arguments']
layout = struct.unpack('>64I', original[:256])
section = next(i for i in range(7) if layout[18 + i] <= 0x8021a120 < layout[18 + i] + layout[36 + i])
offset = layout[section] + 0x8021a120 - layout[18 + section]
assert base64.b64decode(capture['syscallVector']) == original[offset:offset + 28]
image_layout = struct.unpack('>64I', image[:256])
text_section = next(i for i in range(7) if image_layout[18 + i] == 0x80600000)
words = struct.unpack_from('>' + 'I' * (image_layout[36 + text_section] // 4), image, image_layout[text_section])
targets = []
for index, word in enumerate(words):
    if word >> 26 == 18 and word & 1:
        assert not word & 2
        displacement = word & 0x03fffffc
        if displacement & 0x02000000:
            displacement -= 0x04000000
        targets.append(0x80600000 + index * 4 + displacement)
assert targets == [0x8021a140] + [0x80212fd0] * 16
data = base64.b64decode(capture['data'])
assert len(data) == 16 * 736
def verify_case(row, case):
    index, address, length = case['index'], case['address'], case['length']
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    lines = (length + (address & 31) + 31) // 32 if length else 0
    state = list(struct.unpack_from('>13I', row, 24))
    expected = [0x2032, 0xc200, 0x80212ffc if length else 0, 0x2032 if length else 0,
        0x80540000, 0x805335e0, 0x8052e720, 0xc0680000 + index * 736,
        0xc200 if length else 0x11223344, 0xc208 if length else 0x55667788,
        address + lines * 32, lines, case['return']]
    assert state == expected, (index, state, expected)
    for offset in range(0, 160, 4):
        expected_word = ((index + 1) * 0x1020304 + offset * 0x01010101) & 0xffffffff if offset < lines * 32 else 0xa5a5a5a5
        assert struct.unpack_from('>I', row, 128 + offset)[0] == expected_word, (index, offset)
    return state
states = [verify_case(data[i * 736:(i + 1) * 736], case) for i, case in enumerate(generation['records'])]
for offset in (32, 128):
    mutant = bytearray(data[736:1472])
    mutant[offset] ^= 1
    try:
        verify_case(mutant, generation['records'][1])
    except AssertionError:
        pass
    else:
        raise AssertionError('Wrong syscall return or physical payload accepted')
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_DCFLUSH16_CPU_SYSCALL14_ZERO_LENGTH2_PHYSICAL_VISIBILITY_PASS',
    'generationSha256': sha(output / 'generation.json'), 'captureSha256': sha(output / 'fpr-init-true-dolphin.json'),
    'verifierSha256': sha(Path(__file__)), 'states': states, 'mutantsRejected': ['syscall resume', 'physical flush payload'],
    'limits': generation['limits'] + ['No intermediate HID0 sample or physical hardware ordering proof; final r9/r10/HID0 and copied instructions constrain behavior.']}, indent=2) + '\n')
print('PASS16original DCFlushRange:14CPU syscall/rfi returns,2zero-length controls, aligned/unaligned160-byte physical visibility')

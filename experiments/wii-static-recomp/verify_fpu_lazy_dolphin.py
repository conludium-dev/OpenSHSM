"""Verify CPU-delivered original lazy-FPU memcpy against already-enabled controls."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-fpu-lazy')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
capture = json.loads((output / 'fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
for key, name in [('generatorSha256', 'build_fpu_lazy_dolphin.py'), ('parentGeneratorSha256', 'build_si_query_dolphin.py'),
        ('helperSha256', 'build_dolphin_probe.py'), ('baseRunnerSha256', 'run_dolphin_probe.ps1'), ('wrapperSha256', 'run_fpu_lazy_dolphin.ps1')]:
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
for flag in ('Dolphin.Core.CPUCore=0', '-v Null', 'dolphin-fpu-lazy-user'):
    assert flag in capture['arguments']
layout = struct.unpack('>64I', image[:256])
text_section = next(i for i in range(7) if layout[18 + i] == 0x80600000)
words = struct.unpack_from('>' + 'I' * (layout[36 + text_section] // 4), image, layout[text_section])
targets = []
for index, word in enumerate(words):
    if word >> 26 == 18 and word & 1:
        assert not word & 2
        displacement = word & 0x03fffffc
        if displacement & 0x02000000:
            displacement -= 0x04000000
        targets.append(0x80600000 + index * 4 + displacement)
assert targets == [0x80005f34] * 16, 'Fixture must not call the FPU handler directly'
original_layout = struct.unpack('>64I', original[:256])
section = next(i for i in range(7) if original_layout[18 + i] <= 0x80211ba0 < original_layout[18 + i] + original_layout[36 + i])
vector = list(struct.unpack_from('>38I', original, original_layout[section] + 0x80211ba0 - original_layout[18 + section]))
assert vector[26] == 0x38600000
vector[26] = 0x38600007
assert generation['vectorWords'] == vector
data = base64.b64decode(capture['data'])
assert len(data) == 16 * 736
def check_record(row, case):
    index = case['index']
    assert row[:16] == b'OSHSM_PPC_DLP001'
    assert struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    state = list(struct.unpack_from('>11I', row, 24))
    prefix = [0x2032, 0x80501000, 0x800060f4, 0x32, 0] if case['unavailable'] else [0x2032, 0, 0, 0, 0]
    assert state == prefix + [0x80560000, 0x80540000, 0x805335e0, 0x8052e720, 0xc0680000 + index * 736, case['return']]
    expected = struct.pack('>32I', *[((index + 1) * 0x1020304 + offset * 0x01010101) & 0xffffffff for offset in range(0, 128, 4)])
    assert row[128:256] == expected and row[256:384] == expected
    return state
states = [check_record(data[i * 736:(i + 1) * 736], case) for i, case in enumerate(generation['records'])]
for offset in (32, 128):
    mutant = bytearray(data[:736])
    mutant[offset] ^= 1
    try:
        check_record(mutant, generation['records'][0])
    except AssertionError:
        pass
    else:
        raise AssertionError('Corrupted resume PC or copy payload accepted')
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_CPU_LAZY_FPU_COPY8_ENABLED_CONTROLS8_MATCH',
    'generationSha256': sha(output / 'generation.json'), 'captureSha256': sha(output / 'fpr-init-true-dolphin.json'),
    'verifierSha256': sha(Path(__file__)), 'states': states, 'mutantsRejected': ['resume PC', 'destination payload'],
    'limits': generation['limits'] + ['Fixture ABI/copy/owner/MSR/SRR0 checked; no all-register/timing or populated-context save/load claim.']}, indent=2) + '\n')
print('PASS8original CPU-delivered lazy-FPU memcpy +8enabled controls; exact resumePC/owner/MSR/ABI and128-byte copy')

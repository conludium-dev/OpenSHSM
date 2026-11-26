"""Verify whole original memory-protection return and final tables/BAT/MI state."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-memory-protection')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
capture = json.loads((output / 'fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
for key, name in [('generatorSha256', 'build_memory_protection_dolphin.py'), ('parentGeneratorSha256', 'build_si_query_dolphin.py'),
        ('helperSha256', 'build_dolphin_probe.py'), ('baseRunnerSha256', 'run_dolphin_probe.ps1'), ('wrapperSha256', 'run_memory_protection_dolphin.ps1')]:
    assert generation[key] == sha(experiment / name)
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert generation['originalSha256'] == hashlib.sha256(original).hexdigest()
image = (output / 'fpr-init.dol').read_bytes()
assert generation['harnessSha256'] == sha(output / 'fpr-init.dol') == capture['harnessSha256'].lower()
assert capture['scriptSha256'].lower() == generation['wrapperSha256']
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
assert generation['patches'] == [] and image[256:len(original)] == original[256:]
assert capture['records'] == len(generation['records']) == 16 and capture['accurateCache'] == 'True'
for flag in ('Dolphin.Core.CPUCore=0', '-v Null', 'dolphin-memory-protection-user'):
    assert flag in capture['arguments']
layout = struct.unpack('>64I', image[:256])
section = next(i for i in range(7) if layout[18 + i] == 0x80600000)
words = struct.unpack_from('>' + 'I' * (layout[36 + section] // 4), image, layout[section])
calls = []
for index, word in enumerate(words):
    if word >> 26 == 18 and word & 1:
        assert not word & 2
        delta = word & 0x03fffffc
        if delta & 0x02000000:
            delta -= 0x04000000
        calls.append(0x80600000 + index * 4 + delta)
assert calls == [0x80218680] * 16
before_bats = [0x80001fff, 2, 0, 0, 0, 0, 0, 0, 0x80001fff, 2, 0xc0001fff, 0x2a, 0, 0, 0, 0,
    0x90001fff, 0x10000002, 0, 0, 0, 0, 0, 0, 0x90001fff, 0x10000002, 0xd0001fff, 0x1000002a, 0, 0, 0, 0]
after_bats = [0x800001ff, 2, 0, 0, 0x810000ff, 0x01000002, 0, 0, 0x800001ff, 2, 0xc0001fff, 0x2a, 0x810000ff, 0x01000002, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0x900003ff, 0x10000002, 0xd00007ff, 0x1000002a, 0x920001ff, 0x12000002, 0x9300007f, 0x13000002]
data = base64.b64decode(capture['data'])
assert len(data) == 16 * 736
def check_case(row, case):
    index = case['index']
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    scalar = list(struct.unpack_from('>24I', row, 24))
    assert scalar == [0x2032, 0xc200, 0x80540000, 0x805335e0, 0x8052e720, 0xc0680000 + index * 736,
        0x55660000 + index, case['return'], 0x83900000, 1, 0xf7fffff0, 0, 0x8042cfc8, 0x8042cfc8, 0, 0,
        *([0x80218020] * 5), 0xff, 0x10, 0]
    before = list(struct.unpack_from('>32I', row, 160))
    after = list(struct.unpack_from('>32I', row, 320))
    assert before == (before_bats if index == 0 else after_bats) and after == after_bats
    return {'index': index, 'scalar': scalar, 'beforeBats': before, 'afterBats': after}
states = [check_case(data[i * 736:(i + 1) * 736], case) for i, case in enumerate(generation['records'])]
for offset in (60, 108, 112, 320):
    mutant = bytearray(data[:736])
    mutant[offset] ^= 1
    try:
        check_case(mutant, generation['records'][0])
    except AssertionError:
        pass
    else:
        raise AssertionError('Mutated initialized/protection/mask/BAT accepted')
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_MEMORY_PROTECTION8_FIRST8_REPEAT_MI_TABLE_QUEUE_BAT_PASS',
    'generationSha256': sha(output / 'generation.json'), 'captureSha256': sha(output / 'fpr-init-true-dolphin.json'),
    'verifierSha256': sha(Path(__file__)), 'states': states, 'mutantsRejected': ['initialized', 'protection type', 'MI mask', 'BAT'],
    'limits': generation['limits'] + ['Final-state capture; not intermediate BAT transitions or interrupt delivery/protection enforcement.',
        'Repeated calls preserve prior tables/queue/masks/BAT; no second shutdown registration or function execution asserted from state alone.']}, indent=2) + '\n')
print('PASS16whole original memory-protection calls:8first/8repeat,24scalars/32BAT words/table/queue/MI endpoints')

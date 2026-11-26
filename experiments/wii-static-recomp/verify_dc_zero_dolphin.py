"""Verify original line rounding and cached/physical visibility before and after flush."""
from pathlib import Path
import base64
import hashlib
import json
import struct
experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-dc-zero')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
capture = json.loads((output / 'fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
for key, name in [('generatorSha256', 'build_dc_zero_dolphin.py'), ('parentSha256', 'build_si_query_dolphin.py'),
        ('helperSha256', 'build_dolphin_probe.py'), ('wrapperSha256', 'run_dc_zero_dolphin.ps1'), ('baseRunnerSha256', 'run_dolphin_probe.ps1')]:
    assert generation[key] == sha(experiment / name)
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
image = (output / 'fpr-init.dol').read_bytes()
assert generation['originalSha256'] == hashlib.sha256(original).hexdigest()
assert generation['harnessSha256'] == sha(output / 'fpr-init.dol') == capture['harnessSha256'].lower()
assert capture['scriptSha256'].lower() == generation['wrapperSha256']
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
assert generation['patches'] == [] and image[256:len(original)] == original[256:]
assert capture['records'] == 32 and capture['accurateCache'] == 'True'
for flag in ('Dolphin.Core.CPUCore=0', '-v Null', 'dolphin-dc-zero-user'):
    assert flag in capture['arguments']
data = base64.b64decode(capture['data'])
assert len(data) == 32 * 736
def check(row, case):
    index, address, length = case['index'], case['address'], case['length']
    misalignment = address & 31
    count = (length + misalignment + 31) // 32 if length else 0
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    scalar = list(struct.unpack_from('>12I', row, 24))
    assert scalar == [address + count * 32, count if length else 0, misalignment if length else 0xaabbccdd,
        0 if length else 0x12345678, 0x80540000, 0x805335e0, 0x8052e720, 0xc0680000 + index * 736,
        0x55660000 + index, case['return'], 0x2032, 0xc200]
    pattern = struct.pack('>40I', *[((index + 1) * 0x1020304 + offset * 0x01010101) & 0xffffffff for offset in range(0, 160, 4)])
    if not case['warmCache']:
        pattern = bytes([0xa5]) * 160
    cached = bytes(count * 32) + pattern[count * 32:]
    physical = bytes(count * 32) + bytes([0xa5]) * (160 - count * 32)
    assert row[128:288] == cached and row[288:448] == bytes([0xa5]) * 160 and row[448:608] == physical
    return {'scalar': scalar, 'cachedHex': cached.hex(), 'beforeRawHex': row[288:448].hex(), 'afterRawHex': physical.hex(), 'lines': count}
states = [check(data[i * 736:(i + 1) * 736], case) for i, case in enumerate(generation['records'])]
for index, offset in [(1, 128), (1, 288), (1, 448), (8, 36)]:
    mutant = bytearray(data[index * 736:(index + 1) * 736])
    mutant[offset] ^= 1
    try:
        check(mutant, generation['records'][index])
    except AssertionError:
        pass
    else:
        raise AssertionError('Wrong cached/raw visibility or zero-length state accepted')
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_DC_ZERO32_ALIGNMENT_DIRTY_CACHE_FLUSH_VISIBILITY_PASS',
    'generationSha256': sha(output / 'generation.json'), 'captureSha256': sha(output / 'fpr-init-true-dolphin.json'),
    'verifierSha256': sha(Path(__file__)), 'states': states, 'limits': generation['limits']}, indent=2) + '\n')
print('PASS32original DCZeroRange cases: populated/missing cache lines,32-byte rounding/flush visibility/zero-length ABI')

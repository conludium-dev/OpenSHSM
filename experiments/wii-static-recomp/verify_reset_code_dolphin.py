"""Verify unpatched cold/warm reset-code execution, ABI and parameter preservation."""
from pathlib import Path
import base64
import hashlib
import json
import struct
experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-reset-code')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
capture = json.loads((output / 'fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
for key, name in [('generatorSha256', 'build_reset_code_dolphin.py'), ('parentSha256', 'build_si_query_dolphin.py'),
        ('helperSha256', 'build_dolphin_probe.py'), ('wrapperSha256', 'run_reset_code_dolphin.ps1'), ('baseRunnerSha256', 'run_dolphin_probe.ps1')]:
    assert generation[key] == sha(experiment / name)
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
image = (output / 'fpr-init.dol').read_bytes()
assert generation['originalSha256'] == hashlib.sha256(original).hexdigest()
assert generation['harnessSha256'] == sha(output / 'fpr-init.dol') == capture['harnessSha256'].lower()
assert capture['scriptSha256'].lower() == generation['wrapperSha256']
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
assert generation['patches'] == [] and image[256:len(original)] == original[256:]
assert capture['records'] == 16 and capture['accurateCache'] == 'True'
for flag in ('Dolphin.Core.CPUCore=0', '-v Null', 'dolphin-reset-code-user'):
    assert flag in capture['arguments']
data = base64.b64decode(capture['data'])
assert len(data) == 16 * 736
def check(row, case):
    index, flag, value = case['index'], case['flag'], case['value']
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    actual = list(struct.unpack_from('>12I', row, 24))
    assert actual == [(value | 0x80000000) if flag else 0, value if flag else 0, 0x2032,
        0x80540000, 0x805335e0, 0x8052e720, 0xc0680000 + index * 736, 0x55660000 + index, case['return'], flag, value, 0]
    return actual
states = [check(data[i * 736:(i + 1) * 736], case) for i, case in enumerate(generation['records'])]
for index, offset in [(0, 24), (1, 24), (1, 64)]:
    mutant = bytearray(data[index * 736:(index + 1) * 736])
    mutant[offset] ^= 1
    try:
        check(mutant, generation['records'][index])
    except AssertionError:
        pass
    else:
        raise AssertionError('Wrong return or modified reboot parameter accepted')
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_RESET_CODE8_COLD8_WARM_ABI_PARAMETERS_PASS',
    'generationSha256': sha(output / 'generation.json'), 'captureSha256': sha(output / 'fpr-init-true-dolphin.json'),
    'verifierSha256': sha(Path(__file__)), 'states': states, 'limits': generation['limits']}, indent=2) + '\n')
print('PASS16whole original reset-code calls: coldPI0, warmhigh-bit/ABI/parameters retained')

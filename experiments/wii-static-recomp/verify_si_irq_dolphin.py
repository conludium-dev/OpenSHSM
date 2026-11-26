"""Verify callback-present SI/PI transitions through the original handler."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-si-irq')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation_path, capture_path = output / 'generation.json', output / 'fpr-init-true-dolphin.json'
generation = json.loads(generation_path.read_text())
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert generation['generatorSha256'] == sha(experiment / 'build_si_irq_dolphin.py')
assert generation['baseGeneratorSha256'] == sha(experiment / 'build_si_query_dolphin.py')
assert generation['helperSha256'] == sha(experiment / 'build_dolphin_probe.py')
assert generation['baseRunnerSha256'] == sha(experiment / 'run_dolphin_probe.ps1')
assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / 'run_si_irq_dolphin.ps1')
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
assert capture['records'] == len(generation['records']) == 16 and capture['accurateCache'] == 'True'
assert 'Dolphin.Core.CPUCore=0' in capture['arguments'] and '-v Null' in capture['arguments']
for channel in range(4):
    assert f'Dolphin.Core.SIDevice{channel}=0' in capture['arguments']
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert generation['originalSha256'] == sha(original_path)
original, image = original_path.read_bytes(), (output / 'fpr-init.dol').read_bytes()
original_header, header = struct.unpack('>64I', original[:256]), struct.unpack('>64I', image[:256])

def offset(address, layout):
    section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
    return layout[section] + address - layout[18 + section]

def target(address, layout):
    word = struct.unpack_from('>I', image, offset(address, layout))[0]
    assert word >> 26 == 18 and word & 3 == 0
    displacement = word & 0x03fffffc
    if displacement & 0x02000000:
        displacement -= 0x04000000
    return address + displacement

assert {patch['address'] for patch in generation['patches']} == {0x8020fe30, 0x8020fe8c, 0x80210110}
allowed = set()
for patch in generation['patches']:
    assert patch['offset'] == offset(patch['address'], original_header)
    assert struct.unpack_from('>I', original, patch['offset'])[0] == patch['opcode']
    assert target(patch['address'], original_header) == patch['trampoline']
    allowed.update(range(patch['offset'], patch['offset'] + 4))
    if patch.get('kind') == 'callback':
        words = struct.unpack_from('>11I', image, offset(patch['trampoline'], header))
        assert words[:3] == (0x9421ffe0, 0x9161fff8, 0x9181fffc)
        assert words[5:10] == (0x816b0000, 0x906b0068, 0x908b006c, 0x8161fff8, 0x8181fffc)
        assert target(patch['trampoline'] + 40, header) == patch['address'] + 4
    else:
        words = struct.unpack_from('>10I', image, offset(patch['trampoline'], header))
        assert words[:2] == (0x9161fff8, 0x9181fffc)
        assert words[4] == 0x816b0000 and words[5] == 0x900b0000 | patch['slot']
        assert words[6:9] == (0x8161fff8, 0x8181fffc, patch['opcode'])
        assert target(patch['trampoline'] + 36, header) == patch['address'] + 4
assert {i for i in range(256, len(original)) if original[i] != image[i]} <= allowed
data = base64.b64decode(capture['data'])
assert len(data) == 16 * 736
values = []
for case in generation['records']:
    index, channel = case['index'], case['channel']
    assert case['callback'] == 0x80210110
    row = data[index * 736:(index + 1) * 736]
    assert row[:16] == b'OSHSM_PPC_DLP001'
    assert struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    actual = list(struct.unpack_from('>22I', row, 24))
    status = 8 << ((3 - channel) * 8)
    completed = 0xe0010300 | channel << 1
    command = (0xc0010301 if index == 0 else 0xe0010301) | channel << 1
    expected = [1, completed, status, 0, completed, status, 8, 8, 0xa5, 0x60010300 | channel << 1,
        0, channel, 0xffffffff, 0x10000, 0x10008, command, 0, 8, 0x10000, 0, channel, 8]
    assert actual == expected, (index, actual, expected)
    values.append({**case, 'observations': actual})
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_SI_IRQ_HANDLER16_CALLBACK_PI_STATUS_VALIDATED', 'values': values,
    'captureSha256': sha(capture_path), 'generationSha256': sha(generation_path), 'verifierSha256': sha(Path(__file__)),
    'limits': generation['limits'] + ['Field48 is observed callback status, not a return value from void SIInterruptHandler.',
        'Not unpatched control or automatic CPU exception delivery; completion timing/all registers/active device input remain unverified.']}, indent=2) + '\n')
print('PASS16 original callback-present SI packets/handler: PI10000→10008→10000, status cleared, callback consumed/type8')

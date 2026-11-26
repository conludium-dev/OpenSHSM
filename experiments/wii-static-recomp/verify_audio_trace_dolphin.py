"""Verify replaying DSP trace observers against the unpatched whole-function control."""
from pathlib import Path
import base64
import hashlib
import json
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'dolphin-audio-trace'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_audio_init_dolphin.py')], check=True)
generation = json.loads((output / 'generation.json').read_text())
capture = json.loads((output / 'fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
control_capture = json.loads((private / 'dolphin-audio-init/fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
control_proof = json.loads((private / 'dolphin-audio-init/comparison.json').read_text())
for key, name in [('generatorSha256', 'build_audio_trace_dolphin.py'), ('parentGeneratorSha256', 'build_si_query_dolphin.py'),
        ('helperSha256', 'build_dolphin_probe.py'), ('baseRunnerSha256', 'run_dolphin_probe.ps1'), ('wrapperSha256', 'run_audio_trace_dolphin.ps1')]:
    assert generation[key] == sha(experiment / name)
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
original = original_path.read_bytes()
image = (output / 'fpr-init.dol').read_bytes()
assert generation['originalSha256'] == sha(original_path)
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256']
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
assert capture['records'] == len(generation['records']) == 16 and capture['accurateCache'] == 'True'
for flag in ('Dolphin.Core.CPUCore=0', 'Dolphin.Core.DSPHLE=True', '-v Null', 'dolphin-audio-trace-user'):
    assert flag in capture['arguments']
layout = struct.unpack('>64I', image[:256])
def image_offset(address):
    section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
    return layout[section] + address - layout[18 + section]
def branch_target(address, word):
    assert word >> 26 == 18 and word & 3 == 0
    displacement = word & 0x03fffffc
    if displacement & 0x02000000:
        displacement -= 0x04000000
    return address + displacement
allowed = set()
assert len(generation['patches']) == 24
for patch in generation['patches']:
    assert patch['offset'] == image_offset(patch['address'])
    assert struct.unpack_from('>I', original, patch['offset'])[0] == patch['opcode']
    primary = patch['opcode'] >> 26
    assert primary in (36, 40, 44)
    assert patch['kind'] == ('read' if primary == 40 else 'write')
    assert patch['width'] == (4 if primary == 36 else 2)
    assert branch_target(patch['address'], struct.unpack_from('>I', image, patch['offset'])[0]) == patch['trampoline']
    words = patch['words']
    assert list(struct.unpack_from('>' + 'I' * len(words), image, image_offset(patch['trampoline']))) == words
    assert words[:3] == [patch['opcode'], 0x9161fff8, 0x9181fffc]
    assert words[-3:-1] == [0x8161fff8, 0x8181fffc]
    assert branch_target(patch['trampoline'] + (len(words) - 1) * 4, words[-1]) == patch['address'] + 4
    assert not any(word >> 26 in (10, 11) or word >> 26 in (21, 31) and word & 1 for word in words[1:-1])
    allowed.update(range(patch['offset'], patch['offset'] + 4))
assert {i for i in range(256, len(original)) if image[i] != original[i]} == allowed
expected_values = [0x43, 0x8ac, 0x804, 0x805, 0, 0x01000000, 0, 0x20, 0x824,
    0x01000000, 0, 0x20, 0x824, 0x804, 4, 4, 0, 0x8054, 0x4348, 0, 4, 0x8ac, 0x804, 0x805]
data = base64.b64decode(capture['data'])
control = base64.b64decode(control_capture['data'])
assert len(data) == 16 * 1024 and len(control) == 16 * 736
def check_case(row, case):
    index = case['index']
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    final = list(struct.unpack_from('>19I', row, 24))
    expected = list(control_proof['states'][index])
    expected[5] = 0xc0680000 + index * 1024
    expected[7] = case['return']
    assert final == expected
    assert row[128:544] == control[index * 736 + 128:index * 736 + 544]
    assert struct.unpack_from('>I', row, 100)[0] == 24
    events = []
    for number, patch in enumerate(generation['patches']):
        site, value, address, ticks = struct.unpack_from('>4I', row, 544 + number * 16)
        assert site == patch['address'] and value == expected_values[number]
        assert address == 0xcc000000 + (patch['opcode'] & 65535)
        events.append({'site': site, 'value': value, 'address': address, 'ticks': ticks, 'kind': patch['kind'], 'width': patch['width']})
        if number:
            assert 0 < (ticks - events[number - 1]['ticks']) & 0xffffffff < 0x80000000
    assert (events[9]['ticks'] - events[8]['ticks']) & 0xffffffff >= 0x892
    return events
traces = [check_case(data[i * 1024:(i + 1) * 1024], case) for i, case in enumerate(generation['records'])]
for offset in (544 + 17 * 16 + 4, 544 + 8 * 16 + 4, 544 + 9 * 16 + 12):
    mutant = bytearray(data[:1024])
    if offset == 544 + 9 * 16 + 12:
        struct.pack_into('>I', mutant, offset, traces[0][8]['ticks'])
    else:
        mutant[offset] ^= 1
    try:
        check_case(mutant, generation['records'][0])
    except AssertionError:
        pass
    else:
        raise AssertionError('Wrong mailbox/completion or skipped wait accepted')
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_AUDIO_INIT16_DSP24_EVENT_TRACES_UNPATCHED_ENDPOINT_MATCH',
    'generationSha256': sha(output / 'generation.json'), 'captureSha256': sha(output / 'fpr-init-true-dolphin.json'),
    'verifierSha256': sha(Path(__file__)), 'baseGeneratorSha256': sha(experiment / 'build_audio_init_dolphin.py'),
    'unpatchedProofSha256': sha(private / 'dolphin-audio-init/comparison.json'), 'traces': traces,
    'mutantsRejected': ['ready mailbox high', 'DMA completion acknowledgement', 'inter-DMA timer wait'],
    'limits': ['24selected scalar accesses, not every polling read or CPU interrupt trace; observer overhead is not cycle-exact timing.',
        'Original opcodes replay once, scratch registers/CR/LR retained; fixture ABI uses disclosed row-pointer/caller layout remaps,416memory bytes match unpatched control.',
        'DSP HLE emulator reference/prepared arena-IPLandCPU state, not physical Wii or native DSP/full-game/audio acceptance.']}, indent=2) + '\n')
print('PASS16original DSP24-event traces: DMA acknowledgements,80544348 mailbox, tick wait and unpatched endpoints')

"""Verify whole original audio startup return, DSP final registers and DMA/cache payloads."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-audio-init')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
capture = json.loads((output / 'fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
for key, name in [('generatorSha256', 'build_audio_init_dolphin.py'), ('parentGeneratorSha256', 'build_si_query_dolphin.py'),
        ('helperSha256', 'build_dolphin_probe.py'), ('baseRunnerSha256', 'run_dolphin_probe.ps1'), ('wrapperSha256', 'run_audio_init_dolphin.ps1')]:
    assert generation[key] == sha(experiment / name)
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
original = original_path.read_bytes()
image = (output / 'fpr-init.dol').read_bytes()
assert generation['originalSha256'] == sha(original_path)
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256']
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
assert generation['patches'] == [] and image[256:len(original)] == original[256:]
assert capture['records'] == len(generation['records']) == 16 and capture['accurateCache'] == 'True'
for flag in ('Dolphin.Core.CPUCore=0', 'Dolphin.Core.DSPHLE=True', '-v Null', 'dolphin-audio-init-user'):
    assert flag in capture['arguments']
layout = struct.unpack('>64I', original[:256])
section = next(i for i in range(18) if layout[18 + i] <= 0x8042bca0 < layout[18 + i] + layout[36 + i])
firmware_offset = layout[section] + 0x8042bca0 - layout[18 + section]
firmware = original[firmware_offset:firmware_offset + 128]
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
assert targets == [0x8021a140] + [0x80212ce0] * 16
data = base64.b64decode(capture['data'])
assert len(data) == 16 * 736
def check_case(row, case):
    index = case['index']
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    state = list(struct.unpack_from('>19I', row, 24))
    assert state == [0x2032, 0xc200, 0x80540000, 0x805335e0, 0x8052e720, 0xc0680000 + index * 736,
        0x55660000 + index, case['return'], 0x43, 0x804, 0x54, 0x4348, 0x100, 0x20, 0, 0x20, 0, 0, 243000000]
    expected = struct.pack('>32I', *[((index + 1) * 0x1020304 + offset * 0x01010101) & 0xffffffff for offset in range(0, 128, 4)])
    assert row[128:256] == expected and row[384:512] == expected
    assert row[256:384] == firmware and row[512:544] == firmware[:32]
    return state
states = [check_case(data[i * 736:(i + 1) * 736], case) for i, case in enumerate(generation['records'])]
for offset in (64, 128, 512):
    mutant = bytearray(data[:736])
    mutant[offset] ^= 1
    try:
        check_case(mutant, generation['records'][0])
    except AssertionError:
        pass
    else:
        raise AssertionError('Wrong mailbox/restoration/DMA accepted')
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_WHOLE_AUDIO_INIT16_RETURN_REGISTERS_CACHE_BACKUP_DMA_PASS',
    'generationSha256': sha(output / 'generation.json'), 'captureSha256': sha(output / 'fpr-init-true-dolphin.json'),
    'verifierSha256': sha(Path(__file__)), 'firmwareSha256': hashlib.sha256(firmware).hexdigest(), 'states': states,
    'mutantsRejected': ['mailbox', 'restored source', 'DMA payload'], 'limits': generation['limits'] +
        ['Final mailbox read order high then low may consume pending state; no chronological bus/interrupt or intermediate reset/DMA proof.',
        'Physical81000000 retains flushed DSPInitCode while cached view restores original pattern; not a stale-cache failure.',
        'No audible output/full game/all-register/physical Wii or native implementation acceptance.']}, indent=2) + '\n')
print('PASS16whole original OS audio startups: final DSP/mailbox/ABI/cache restoration and32-byte MEM2 DMA')

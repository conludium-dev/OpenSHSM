"""Verify original transport/consumed MEM2 packet, positive STM and missing-device controls."""
from pathlib import Path
import base64
import hashlib
import json
import struct
import sys

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
startup = '--startup-control' in sys.argv
name = 'dolphin-stm-open-startup' if startup else 'dolphin-stm-open'
wrapper = 'run_stm_open_startup_dolphin.ps1' if startup else 'run_stm_open_dolphin.ps1'
output = root / name
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
for key, path in [('generatorSha256', experiment / 'build_stm_open_dolphin.py'),
    ('parentSha256', experiment / 'build_si_query_dolphin.py'), ('helperSha256', experiment / 'build_dolphin_probe.py'),
    ('baseRunnerSha256', experiment / 'run_dolphin_probe.ps1'), ('wrapperSha256', experiment / wrapper)]:
    assert generation[key] == sha(path)
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
original = original_path.read_bytes()
image = (output / 'fpr-init.dol').read_bytes()
assert generation['patches'] == [] and image[256:len(original)] == original[256:]
assert generation['originalSha256'] == sha(original_path)
assert generation['harnessSha256'] == sha(output / 'fpr-init.dol') == capture['harnessSha256'].lower()
assert capture['scriptSha256'].lower() == generation['wrapperSha256']
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
assert capture['records'] == len(generation['records']) == 16 and capture['accurateCache'] == 'True'
assert all(flag in capture['arguments'] for flag in ('Dolphin.Core.CPUCore=0', '-v Null', name + '-user'))
layout = struct.unpack('>64I', original[:256])
def original_bytes(address, size):
    section = next(i for i in range(18) if layout[18 + i] <= address and address + size <= layout[18 + i] + layout[36 + i])
    offset = layout[section] + address - layout[18 + section]
    return original[offset:offset + size]
assert original_bytes(0x804398f0, 19) == b'/dev/stm/immediate\0'
assert original_bytes(0x802423bc, 4).hex() == '546006b6'
assert original_bytes(0x802423c4, 4).hex() == '60040001'
image_layout = struct.unpack('>64I', image[:256])
section = next(i for i in range(7) if image_layout[18 + i] == 0x80600000)
words = struct.unpack_from('>' + 'I' * (image_layout[36 + section] // 4), image, image_layout[section])
targets = []
for index, word in enumerate(words):
    if word >> 26 == 18 and word & 1:
        assert not word & 2
        displacement = word & 0x03fffffc
        if displacement & 0x02000000:
            displacement -= 0x04000000
        targets.append(0x80600000 + index * 4 + displacement)
assert targets == [0x80241c30] * 96
data = base64.b64decode(capture['data'])
assert len(data) == 16 * 736
send = 0x31 if startup else 0x39
def check(row, case):
    index, physical = case['index'], case['physical']
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    state = list(struct.unpack_from('>18I', row, 24))
    expected = [0x38, 0, send, (send & 0x38) | 2, 0, 0x10000,
        (send & 0x38) | 4, physical, 0x10000, send & 0x38, 0, 0, 0x14000,
        0x2032, physical, 0, physical, case['messageReturn']]
    assert state == expected, (index, state, expected)
    result = index if index < 8 else -6
    packet = row[192:256]
    expected_packet = struct.pack('>5I', 8, result & 0xffffffff, 1, case['pathAddress'], 0) + bytes(44)
    assert packet == expected_packet
    return {'index': index, 'physical': physical, 'states': state, 'replyResult': result, 'replyPacketHex': packet.hex()}
observations = [check(data[i * 736:(i + 1) * 736], case) for i, case in enumerate(generation['records'])]
for offset in (36, 52, 64, 68, 196, 204):
    row = bytearray(data[:736])
    row[offset] ^= 1
    try:
        check(row, generation['records'][0])
    except AssertionError:
        pass
    else:
        raise AssertionError('Wrong ACK/reply/timeout/payload accepted')
ghidra_dir = root / 'ipc-sdk-roots/ghidra'
ghidra = json.loads((ghidra_dir / 'verification.json').read_text())
record = next(row for row in ghidra['records'] if row['name'] == 'IPCWriteReg')
assert record['assemblySha256'] == sha(ghidra_dir / 'IPCWriteReg.asm')
assert record['decompiledSha256'] == sha(ghidra_dir / 'IPCWriteReg.c')
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_MEM2_STM_OPEN8_MISSING8_ACK_REPLY64_MODE0_PASS',
    'verifierSha256': sha(Path(__file__)), 'generationSha256': sha(output / 'generation.json'),
    'captureSha256': sha(capture_path), 'observations': observations, 'mutantsRejected': 6,
    'limits': generation['limits'] + ['PI samples are delayed projections, not cycle-exact IRQ chronology or original IRQ delivery.']}, indent=2) + '\n')
print('PASS originalMEM2 mode0 STM8/missing8; ACK/reply pointer/full64bytes/results +6mutants; send=' + hex(send))

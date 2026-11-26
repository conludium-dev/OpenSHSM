"""Verify CPU IRQ27/rfi, real wait-node wakeup and separate physical/cache visibility."""
from pathlib import Path
import base64
import hashlib
import json
import struct
import sys

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
cached = '--cached' in sys.argv
name = 'dolphin-stm-irq-cache' if cached else 'dolphin-stm-irq'
builder = 'build_stm_irq_cache_dolphin.py' if cached else 'build_stm_irq_dolphin.py'
wrapper = 'run_stm_irq_cache_dolphin.ps1' if cached else 'run_stm_irq_dolphin.ps1'
output = root / name
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
for key, path in [('generatorSha256', experiment / builder), ('parentSha256', experiment / 'build_si_query_dolphin.py'),
    ('parentGeneratorSha256', experiment / 'build_stm_open_dolphin.py'), ('helperSha256', experiment / 'build_dolphin_probe.py'),
    ('wrapperSha256', experiment / wrapper), ('baseRunnerSha256', experiment / 'run_dolphin_probe.ps1'),
    ('contextEvidenceSha256', root / 'mass-ipc-irq-context-observer/irq-context.json')]:
    assert generation[key] == sha(path)
if cached:
    assert generation['cacheParentSha256'] == sha(experiment / 'build_stm_irq_dolphin.py')
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
original = original_path.read_bytes()
image = (output / 'fpr-init.dol').read_bytes()
assert generation['patches'] == [] and image[256:len(original)] == original[256:]
assert generation['originalSha256'] == sha(original_path)
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256']
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
assert capture['accurateCache'] == 'True' and capture['records'] == len(generation['records']) == 16
assert all(flag in capture['arguments'] for flag in ('Dolphin.Core.CPUCore=0', '-v Null', name + '-user'))
layout = struct.unpack('>64I', original[:256])
section = next(i for i in range(7) if layout[18 + i] <= 0x80211ba0 < layout[18 + i] + layout[36 + i])
offset = layout[section] + 0x80211ba0 - layout[18 + section]
vector = list(struct.unpack_from('>38I', original, offset))
assert vector[26] == 0x38600000
vector[26] = 0x38600004
assert generation['vectorWords'] == vector
assert list(struct.unpack('>38I', base64.b64decode(capture['vectorCode']))) == vector
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
assert targets == [0x80241c30] * 64
data = base64.b64decode(capture['data'])
assert len(data) == 16 * 736
def check(row, case):
    index, physical = case['index'], case['physical']
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    state = list(struct.unpack_from('>31I', row, 24))
    expected = [0x38, 0, 0x38, physical, 0x10000, 1, 0, 1, 0x4000, 0x80492658, 0,
        0x80690000, 0x80690000, 0xa032, physical, 0, physical, case['messageReturn'],
        state[20], 27, state[20], 0xa032, 0x80540000, 0x805335e0, 0x8052e720,
        0xc0680000 + index * 736, 0x00010001, 17, 0x804929f8, 0, 0]
    assert state == expected, (index, state, expected)
    assert case['wait'] <= state[20] < case['waitEnd']
    result = index if index < 8 else -6
    expected_packet = bytearray(struct.pack('>5I', 8, result & 0xffffffff, 1, case['pathAddress'], 0) + bytes(44))
    struct.pack_into('>2I', expected_packet, 44, 0x80690000, 0x80690000)
    assert row[192:256] == expected_packet
    if cached:
        struct.pack_into('>2I', expected_packet, 44, 0, 0)
        assert row[256:320] == expected_packet
    return {'index': index, 'states': state, 'physicalPacketHex': row[192:256].hex(),
        'cachedPacketHex': row[256:320].hex() if cached else None, 'replyResult': result}
observations = [check(data[i * 736:(i + 1) * 736], case) for i, case in enumerate(generation['records'])]
locations = [64, 76, 100, 104, 128, 136, 196, 236] + ([300] if cached else [])
for location in locations:
    mutant = bytearray(data[:736])
    mutant[location] ^= 1
    try:
        check(mutant, generation['records'][0])
    except AssertionError:
        pass
    else:
        raise AssertionError('IRQ/context/queue/payload mutation accepted')
ghidra = {}
for directory in ('ios-ipc-interrupt', 'ios-reply-handler', 'ios-wakeup', 'ios-exception-vector', 'ios-irq-dispatch', 'ios-load-context'):
    path = root / directory / 'ghidra/verification.json'
    proof = json.loads(path.read_text())
    for row in proof['records']:
        assert row['assemblySha256'] == sha(path.parent / (row['name'] + '.asm'))
        assert row['decompiledSha256'] == sha(path.parent / (row['name'] + '.c'))
    ghidra[directory] = sha(path)
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_CPU_IPC_IRQ27_16_WAITNODE_WAKES_READY_RFI_CACHE_VISIBILITY_PASS',
    'verifierSha256': sha(Path(__file__)), 'generationSha256': sha(output / 'generation.json'),
    'captureSha256': sha(capture_path), 'ghidraEvidence': ghidra, 'observations': observations,
    'mutantsRejected': len(locations), 'limits': generation['limits']}, indent=2) + '\n')
print('PASS16original CPU IRQ27/reply/WakeupThread/state4→1/readyqueue/rfi; ' + str(len(locations)) + 'mutants; cached=' + str(cached))

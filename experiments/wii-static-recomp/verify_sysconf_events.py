"""Validate replay code, unobserved endpoints and first original async OPEN/READ/free order."""
from pathlib import Path
import base64
import hashlib
import json
import struct
import subprocess
from collections import Counter

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'dolphin-sysconf-events-fixed-disc'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_sysconf_chain.py')], check=True)
generation_path = root / 'dolphin-sysconf-events-fixed/generation.json'
generation = json.loads(generation_path.read_text())
preparation = json.loads((output / 'preparation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
control_path = root / 'dolphin-sysconf-long-disc/fpr-init-true-dolphin.json'
control = json.loads(control_path.read_text(encoding='utf-8-sig'))
original = (root / 'dolphin-sysconf-long/fpr-init.dol').read_bytes()
image = (output / 'DATA/sys/main.dol').read_bytes()
assert sha(experiment / 'build_sysconf_events_dolphin.py') == generation['generatorSha256']
assert sha(experiment / 'run_sysconf_events_fixed_disc_dolphin.ps1') == generation['wrapperSha256']
assert preparation['preparerSha256'] == sha(experiment / 'prepare_sysconf_events_fixed_disc.py')
assert sha(output / 'DATA/sys/main.dol') == generation['harnessSha256'] == capture['harnessSha256'].lower()
assert capture['scriptSha256'].lower() == generation['wrapperSha256']
assert capture['emulatorSha256'].lower() == control['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
assert capture['accurateCache'] == 'True' and capture['records'] == 16
assert generation['controlGenerationSha256'] == sha(root / 'dolphin-sysconf-long/generation.json')
assert generation['eventStride'] == 1280 and generation['eventCapacity'] == 256 and len(generation['patches']) == 9
layout = struct.unpack('>64I', image[:256])
original_layout = struct.unpack('>64I', original[:256])
baseline = bytearray(original)


def words_at(address, count):
    slot = next(i for i in range(7) if layout[18 + i] <= address and address + count * 4 <= layout[18 + i] + layout[36 + i])
    return list(struct.unpack_from('>' + str(count) + 'I', image, layout[slot] + address - layout[18 + slot]))


def target(address, word):
    assert word >> 26 == 18 and not word & 3
    displacement = word & 0x3fffffc
    return address + displacement - (0x4000000 if displacement & 0x2000000 else 0)


save = [0x9001ffe0, 0x9161ffe4, 0x9181ffe8, 0x7c000026, 0x9001ffec, 0x7c0000a6, 0x9001fff0]
index_code = [0x5580502a, 0x558c402e, 0x7d806214, 0x7d6b6214, 0x396b0040]
restore = [0x8001ffec, 0x7c0ff120, 0x8161ffe4, 0x8181ffe8, 0x8001fff0, 0x7c000124, 0x8001ffe0]
for patch in generation['patches']:
    address, offset = patch['address'], patch['offset']
    assert struct.unpack_from('>I', original, offset)[0] == patch['opcode']
    assert target(address, struct.unpack_from('>I', image, offset)[0]) == patch['trampoline']
    assert words_at(patch['trampoline'], len(save)) == save
    span = words_at(patch['trampoline'], (patch['end'] - patch['trampoline']) // 4)
    index_start = next(i for i in range(len(span) - 4) if span[i:i + 5] == index_code)
    assert words_at(patch['restore'], 7) == restore
    assert words_at(patch['end'] - 8, 1) == [patch['opcode']]
    assert target(patch['end'] - 4, words_at(patch['end'] - 4, 1)[0]) == address + 4
    for count in range(256):
        regs = [0] * 32
        regs[11], regs[12] = 0xc06e0000, count
        for word in span[index_start:index_start + 5]:
            op, rs, ra = word >> 26, (word >> 21) & 31, (word >> 16) & 31
            if op == 21:
                shift, mb, me = (word >> 11) & 31, (word >> 6) & 31, (word >> 1) & 31
                value = regs[rs]
                rotated = ((value << shift) | (value >> (32 - shift))) & 0xffffffff
                mask = sum(1 << (31 - bit) for bit in range(mb, me + 1))
                regs[ra] = rotated & mask
            elif op == 31:
                assert (word >> 1) & 1023 == 266 and not (word >> 10) & 1
                regs[rs] = (regs[ra] + regs[(word >> 11) & 31]) & 0xffffffff
            else:
                assert op == 14
                regs[rs] = (regs[ra] + (word & 65535)) & 0xffffffff
        assert regs[11] == 0xc06e0040 + count * 1280
    struct.pack_into('>I', baseline, offset, struct.unpack_from('>I', image, offset)[0])
assert image[256:len(original)] == baseline[256:]
main_slot = next(i for i in range(7) if original_layout[18 + i] == 0x80600000)
assert words_at(0x80600000, original_layout[36 + main_slot] // 4) == list(struct.unpack_from(
    '>' + str(original_layout[36 + main_slot] // 4) + 'I', original, original_layout[main_slot]))

data, golden = base64.b64decode(capture['data']), base64.b64decode(control['data'])
assert len(data) == len(golden) == 16 * 736
for index in range(5, 16):
    row, old = data[index * 736:(index + 1) * 736], golden[index * 736:(index + 1) * 736]
    for start, end in [(16, 24), (36, 80), (80, 100), (192, 320), (400, 408), (416, 512), (608, 620), (644, 648), (720, 732)]:
        assert row[start:end] == old[start:end]
assert base64.b64decode(capture['confPhysical']) == base64.b64decode(control['confPhysical'])
raw = base64.b64decode(capture['events'])
assert len(raw) == 0x50040 and raw[:16] == b'OSHSM_SC_EVENTS1'
count, overflow = struct.unpack_from('>2I', raw, 16)
assert count == 115 and overflow == 0
events = [raw[64 + i * 1280:64 + (i + 1) * 1280] for i in range(count)]
assert Counter(struct.unpack_from('>I', row)[0] for row in events) == {1: 2, 2: 6, 3: 2, 4: 2, 5: 2, 6: 6, 7: 6, 8: 19, 9: 70}
patches = {patch['kind']: patch for patch in generation['patches']}
for row in events:
    kind, address = struct.unpack_from('>2I', row)
    assert patches[kind]['address'] == address
    assert struct.unpack_from('>I', row, 16)[0] in (0x30, 0x32, 0x2032, 0xa032)


def check_open(rows):
    send, control_send, returned, ack, reply, isfs, nand, sc = rows[47:55]
    assert struct.unpack_from('>I', send)[0] == 9
    assert struct.unpack_from('>2I', send, 24) == (0, 0x135e0080)
    assert struct.unpack_from('>2I', control_send, 24) == (1, 0x31)
    header = struct.pack('>8I', 1, 0, 0, 0x135e1020, 1, 1, 0x8053ff90, 0)
    tail = struct.pack('>2I', 0x80240680, 0x935e1020) + bytes(24)
    assert send[64:128] == returned[64:128] == header + tail
    assert send[128:192] == returned[128:192] == header + bytes(32)
    assert struct.unpack_from('>3I', returned, 24) == (0, 0x2032, 0x935e0080)
    assert struct.unpack_from('>I', returned, 16)[0] == 0xa032
    assert struct.unpack_from('>2I', ack, 24) == (1, 0x32) and struct.unpack_from('>2I', reply, 24) == (1, 0x34)
    new_header = struct.pack('>8I', 8, 3, 1, 0x135e1020, 1, 1, 0x8053ff90, 0)
    assert isfs[64:128] == new_header + tail and isfs[128:192] == new_header + bytes(32)
    assert struct.unpack_from('>2I', isfs, 24) == (3, 0x935e1020)
    assert struct.unpack_from('>2I', nand, 24) == (3, 0x804b3094)
    assert struct.unpack_from('>2I', sc, 24) == (0, 0x804b3094)
    for row in (isfs, nand, sc, rows[55], rows[56], rows[57], rows[58], rows[59], rows[60]):
        assert struct.unpack_from('>I', row, 16)[0] == 0x32
    assert isfs[320:384] == b'/shared2/sys/SYSCONF'.ljust(64, b'\0')
    assert struct.unpack_from('>3I', isfs, 576) == (0x80244e30, 0x804b3094, 0)
    assert struct.unpack_from('>I', sc, 648)[0] == 3 and sc[640 + 0x91:640 + 0x93] == bytes([2, 1])
    assert struct.unpack_from('>2I', rows[55], 24) == (0, 0x135e00e0)
    read_header = struct.pack('>8I', 3, 0, 3, 0x4b31a0, 0x4000, 0, 0, 0)
    assert rows[55][192:256] == read_header + struct.pack('>2I', 0x80240680, 0x935e1180) + bytes(24)
    assert rows[55][256:320] == read_header + bytes(32)
    assert struct.unpack_from('>I', rows[57])[0] == 6 and struct.unpack_from('>I', rows[57], 32)[0] == 0x935e1020
    assert struct.unpack_from('>2I', rows[58], 24) == (1, 0x935e1020)
    assert struct.unpack_from('>I', rows[59])[0] == 7 and struct.unpack_from('>I', rows[59], 32)[0] == 0x935e0080
    assert struct.unpack_from('>2I', rows[60], 24) == (0, 0x935e0080)
    assert struct.unpack_from('>I', rows[57], 36)[0] == 0x935e0120
    assert struct.unpack_from('>I', rows[57], 640 + 0x98)[0] == 0x80247800


check_open(events)
mutants = 0
for index, offset in [(47, 76), (47, 96), (49, 24), (49, 128), (50, 28), (52, 24),
    (52, 576), (53, 24), (54, 24), (54, 648), (55, 196), (55, 236), (55, 256),
    (57, 36), (57, 640 + 0x98), (58, 28), (59, 32), (60, 28), (55, 16)]:
    changed = list(events)
    row = bytearray(changed[index])
    row[offset] ^= 1
    changed[index] = bytes(row)
    try:
        check_open(changed)
    except AssertionError:
        mutants += 1
assert mutants == 19
(output / 'events-comparison.json').write_text(json.dumps({'result': 'ORIGINAL_ASYNC_OPEN_RETURN_ACK_REPLY_CALLBACK_REENTRANT_READ_FREE_ORDER_PASS',
    'verifierSha256': sha(Path(__file__)), 'generationSha256': sha(generation_path), 'captureSha256': sha(capture_path),
    'controlCaptureSha256': sha(control_path), 'eventCount': count, 'patches': generation['patches'],
    'mutantsRejected': mutants, 'firstOpen': {'send': 47, 'return': 49, 'ack': 50, 'reply': 51,
        'isfsCallback': 52, 'nandCallback': 53, 'scCallback': 54, 'readSend': 55,
        'workFree': 58, 'packetFree': 60, 'callbackMsr': '32', 'newReadPacket': '135e00e0', 'newReadWork': '935e1180'},
    'limits': ['Observer EE suppression/read/scratch/timing changes; unobserved endpoints match, NOT cycle or all-register equivalence.',
        'First work block snapshot only, no full second work block; no physical retail bootstrap or native integration proof.',
        'Prepared thread/arena/DevKit fallback and isolated emulator-generated system settings; not game assets/public import dependency.']}, indent=2) + '\n')
print('PASS115 original events/9 replay sites/256 stride checks/endpoints unchanged/first asyncOPEN+READ+free order/MSR32;19mutants')

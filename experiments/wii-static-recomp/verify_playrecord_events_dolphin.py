"""Check original callback order against the unchanged unobserved endpoints."""
from pathlib import Path
import base64
from collections import Counter
import hashlib
import json
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'dolphin-playrecord-events-disc'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_playrecord_events_fixture.py')], check=True)
subprocess.run(['python3', str(experiment / 'verify_playrecord_start_dolphin.py')], check=True)
generation_path = root / 'dolphin-playrecord-events/generation.json'
generation = json.loads(generation_path.read_text())
preparation = json.loads((output / 'preparation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
control_path = root / 'dolphin-playrecord-start-disc/fpr-init-true-dolphin.json'
control = json.loads(control_path.read_text(encoding='utf-8-sig'))
assert preparation['preparerSha256'] == sha(experiment / 'prepare_playrecord_events_disc.py')
assert sha(output / 'DATA/sys/main.dol') == generation['harnessSha256'] == capture['harnessSha256'].lower()
assert capture['scriptSha256'].lower() == generation['wrapperSha256']
assert capture['emulatorSha256'].lower() == control['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
assert capture['records'] == 16 and capture['accurateCache'] == 'True'
for key in ('data', 'confPhysical', 'productPhysical', 'inquiryPhysical', 'ticketViewPhysical',
    'ticketScalarsPhysical', 'consumptionCountPhysical', 'consumptionScalarsPhysical',
    'closeScalarsPhysical', 'playrecordStartScalars'):
    assert base64.b64decode(capture[key]) == base64.b64decode(control[key])
lab_path = Path('_scratch/tmp/dolphin-playrecord-events-disc-user/Wii/title/00000001/00000002/data/play_rec.dat')
lab = base64.b64decode(capture['playrecordLabFile'])
assert len(lab) == 128 and lab == lab_path.read_bytes() == base64.b64decode(capture['playrecordBufferPhysical'])
raw = base64.b64decode(capture['events'])
assert len(raw) == 0x50040 and raw[:16] == b'OSHSM_SC_EVENTS1'
count, overflow = struct.unpack_from('>2I', raw, 16)
assert (count, overflow) == (189, 0)
events = [raw[64 + i * 1280:64 + (i + 1) * 1280] for i in range(count)]
assert Counter(struct.unpack_from('>I', row)[0] for row in events) == {1:121, 2:4, 3:9, 4:3, 5:9, 6:32, 7:11}
patches = {patch['kind']: patch for patch in generation['patches']}
for row in events:
    kind, address = struct.unpack_from('>2I', row)
    assert address == patches[kind]['address']

checks = []


def expect(index, offset, payload):
    checks.append((index, offset, payload))


for index, kind, state, r3, r4 in [(150,2,0,0,0), (151,1,1,0,0x135e0080),
    (159,3,1,4,0x935e1020), (160,4,1,4,0x8049325c), (161,2,1,0,0x8049325c),
    (162,1,2,0,0x135e00e0), (165,6,2,1,0x935e1020), (167,6,2,0,0x935e0080),
    (171,3,2,128,0x935e1180), (172,2,2,128,0x8049325c),
    (173,1,3,0,0x135e0080), (176,6,3,1,0x935e1180), (178,6,3,0,0x935e00e0),
    (182,3,3,0,0x935e1020), (183,2,3,0,0x8049325c),
    (185,6,4,1,0x935e1020), (187,6,4,0,0x935e0080)]:
    expect(index, 0, struct.pack('>2I', kind, patches[kind]['address']))
    expect(index, 16, struct.pack('>I', 0x2032 if index <= 151 else 0x32))
    expect(index, 24, struct.pack('>2I', r3, r4))
    expect(index, 1056, struct.pack('>I', state))
expect(151, 64, struct.pack('>8I',1,0,0,0x135e1020,3,2,0x8053ff90,0))
expect(159, 64, struct.pack('>8I',8,4,1,0x135e1020,3,2,0x8053ff90,0))
expect(159, 320, b'/title/00000001/00000002/data/play_rec.dat'.ljust(64, b'\0'))
expect(159, 576, struct.pack('>3I',0x80244e30,0x8049325c,0))
expect(161, 768, struct.pack('>I',4))
expect(162, 192, struct.pack('>8I',3,1,4,0x493120,128,32,0x80492260,32))
expect(171, 192, struct.pack('>8I',8,128,3,0x80493120,128,32,0x80492260,32))
expect(173, 64, struct.pack('>8I',5,4,4,0,0,2,0x8053ff90,0))
expect(182, 64, struct.pack('>8I',8,0,5,0,0,2,0x8053ff90,0))
expect(184, 1056, struct.pack('>9I',4,1,0,0,0,0,0,0,0))
expect(188, 36, struct.pack('>I',0x935e0060))
for index in (171,172,183,184,188):
    expect(index, 640, lab)
for index in (151,161,172,183,188):
    expect(index, 916, struct.pack('>2I',0x8021cde0,0x804931d0))


def check(rows):
    for index, offset, payload in checks:
        assert rows[index][offset:offset + len(payload)] == payload


check(events)
locations = sorted({(index, offset + delta) for index, offset, payload in checks for delta in range(len(payload))})
for index, offset in locations:
    changed = list(events)
    row = bytearray(changed[index])
    row[offset] ^= 1
    changed[index] = bytes(row)
    try:
        check(changed)
    except AssertionError:
        pass
    else:
        raise AssertionError('Unchecked callback evidence mutation')
swaps = [(160,161), (161,162), (162,165), (165,167), (172,173), (173,176), (183,185), (185,187)]
for first, second in swaps:
    changed = list(events)
    changed[first], changed[second] = changed[second], changed[first]
    try:
        check(changed)
    except AssertionError:
        pass
    else:
        raise AssertionError('Unchecked callback/free order swap')
(output / 'playrecord-events-comparison.json').write_text(json.dumps({
    'result':'ORIGINAL_PLAYRECORD_OPEN_READ128_SEEK_CALLBACK_FREE_ORDER_PASS',
    'verifierSha256':sha(Path(__file__)), 'generationSha256':sha(generation_path),
    'captureSha256':sha(capture_path), 'controlCaptureSha256':sha(control_path),
    'eventCount':count, 'fieldMutantsRejected':len(locations), 'orderSwapsRejected':len(swaps),
    'sourceEndpoint':{'state':4, 'get':1, 'fd':4, 'heapFreeHead':'935E0060'},
    'limits':['Original PPC under Dolphin LAB IOS, not physical Wii IOS/timing.',
        'Full unobserved controls and previous outputs unchanged; EE suppression/stack scratch/read/timing perturbations remain.',
        'Buffer already matches the LAB file before READ; callback r3=128 proves returned length, no buffer-transition claim.',
        'No source WRITE/close/alarm firing demonstrated; native OPEN still not submitted and no first screen.']}, indent=2) + '\n')
print(f'PASS189 original events/OPEN FD4/READ callback128/SEEK0/state4-get1/free0060; {len(locations)}field mutations/{len(swaps)}order swaps; endpoints unchanged')

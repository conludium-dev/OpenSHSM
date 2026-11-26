"""Verify original concurrent inquiry/ES snapshots and replay provenance."""
from pathlib import Path
import base64
import json
import struct
from collections import Counter

parent = Path('experiments/wii-static-recomp/verify_sysconf_events.py')
body = parent.read_text().split('\ndata, golden =', 1)[0]
for old, new in [
    ('verify_sysconf_chain.py', 'verify_di_burst_dolphin.py'),
    ('dolphin-sysconf-events-fixed', 'dolphin-di-burst-events'),
    ('dolphin-sysconf-long', 'dolphin-di-burst'),
    ('build_sysconf_events_dolphin.py', 'build_di_burst_events_dolphin.py'),
    ('run_sysconf_events_fixed_disc_dolphin.ps1', 'run_di_burst_events_disc_dolphin.ps1'),
    ('prepare_sysconf_events_fixed_disc.py', 'prepare_di_burst_events_disc.py')]:
    body = body.replace(old, new)
exec(compile(body, str(parent), 'exec'), globals())
assert generation['eventsParentGeneratorSha256'] == sha(experiment / 'build_sysconf_events_dolphin.py')
regions = [(320, 0x804983a0, 320), (640, 0x80492260, 96),
    (736, 0xd35e0140, 64), (800, 0x935e0140, 64), (864, 0x804b2a80, 80),
    (944, 0x8052ac28, 64), (1040, 0x800030c0, 64), (1104, 0x80492920, 64),
    (1216, 0x8052ac78, 32), (1248, 0x935e2560, 32)]
globals_at = [0x800000c0, 0x800000d4, 0x800000e4, 0x800000d8,
    0x80492920, 0x80492934, 0x80528ce8, 0x8052ac44, 0x8052ac50,
    0x8052ab04, 0x935e016c, 0x935e0170]
for patch in generation['patches']:
    span = words_at(patch['trampoline'], (patch['end'] - patch['trampoline']) // 4)
    for slot, address, size in regions + [(1168 + i * 4, address, 4) for i, address in enumerate(globals_at)]:
        expected = [0x3d800000 | (address >> 16), 0x618c0000 | (address & 65535)]
        for byte in range(0, size, 4):
            expected.extend([0x800c0000 | byte, 0x900b0000 | (slot + byte)])
        assert sum(span[i:i + len(expected)] == expected for i in range(len(span) - len(expected) + 1)) == 1
for key in ('data', 'confPhysical', 'productPhysical', 'inquiryPhysical'):
    assert base64.b64decode(capture[key]) == base64.b64decode(control[key])
raw = base64.b64decode(capture['events'])
assert len(raw) == 0x50040 and raw[:16] == b'OSHSM_SC_EVENTS1'
assert struct.unpack_from('>2I', raw, 16) == (118, 0)
events = [raw[64 + i * 1280:64 + (i + 1) * 1280] for i in range(118)]
assert Counter(struct.unpack_from('>I', row)[0] for row in events) == {1: 91, 8: 9, 9: 9, 5: 2, 2: 2, 3: 2, 4: 1, 6: 1, 7: 1}
sites = {patch['kind']: patch['address'] for patch in generation['patches']}
payload = base64.b64decode(capture['inquiryPhysical'])
assert len(payload) == 32


def word(row, offset):
    return struct.unpack_from('>I', row, offset)[0]


def check(rows):
    for row in rows:
        assert word(row, 4) == sites[word(row, 0)]
    for index, kind, msr, r3, r4 in [
        (93, 1, 0x2032, 0, 0x135e0080), (95, 4, 0x2032, 1, 0x2032),
        (96, 8, 0x2032, 0x935e016c, 0), (97, 9, 0x2032, 0x80490000, 0),
        (99, 1, 0x30, 0, 0x135e00e0), (102, 1, 0x30, 0, 0x135e0140),
        (106, 2, 0x32, 1, 0x804983a0), (107, 3, 0x32, 1, 0x804983a0),
        (111, 5, 0x2032, 0, 0x2032), (113, 2, 0x32, 1, 0x804983c0),
        (114, 6, 0x32, 1, 0x804983c0), (115, 7, 0x32, 32, 0x80492280),
        (116, 3, 0x32, 0, 0x32)]:
        row = rows[index]
        assert (word(row, 0), word(row, 16), word(row, 24), word(row, 28)) == (kind, msr, r3, r4)
    for index in (99, 102):
        assert word(rows[index], 12) == 0x8024204c
    idle = rows[97]
    assert struct.unpack_from('>12I', idle, 1168) == (
        0x492658, 0x80492658, 0, 0x80492658, 0x40001, 0x935e016c,
        0xffffffff, 14, 0x80492280, 1, 0x80492658, 0x80492658)
    assert struct.unpack_from('>2I', idle, 52) == (17, 19)
    assert word(idle, 36) == 0x935e0180
    headers = [(64, [6, 3, 3, 0x86, 0x135e2560, 32, 0, 0], 0x804983a0),
        (192, [6, 0, 3, 0x12, 0x135e2580, 32, 0x492260, 32], 0x804983c0)]
    for offset, fields, state in headers:
        header = struct.pack('>8I', *fields)
        assert idle[offset:offset + 64] == header + struct.pack('>2I', 0x802258a0, state) + bytes(24)
        assert idle[offset + 64:offset + 128] == header + bytes(32)
    assert idle[800:864] == struct.pack('>16I', 1, 0, 0, 0x528cf0, 0, 0, 0, 0, 0, 0, 0, 0x80492658, 0x80492658, 0, 0, 0)
    for index, packet in [(105, 0x935e0080), (109, 0x935e0140), (112, 0x935e00e0)]:
        row = rows[index]
        assert (word(row, 12), word(row, 16), word(row, 24), word(row, 28), word(row, 32)) == (0x80241cec, 0x30, 1, 0x34, packet)
    for index in (106, 107):
        assert rows[index][64:96] == rows[index][128:160] == struct.pack('>8I', 8, 1, 6, 0x86, 0x135e2560, 32, 0, 0)
        assert word(rows[index], 36) == 0x935e0180
        assert word(rows[index], 328) == (0x1000000 if index == 106 else 0)
    assert word(rows[108], 36) == 0x935e0060
    assert word(rows[111], 1192) == 4 and word(rows[111], 1188) == 0
    assert rows[111][800:864] == struct.pack('>16I', 8, 4, 1, 0x528cf0, *([0] * 12))
    for index in (113, 114, 115, 116, 117):
        row = rows[index]
        assert row[640:672] == payload
        assert row[192:224] == struct.pack('>8I', 8, 1, 6, 0x12, 0x135e2580, 32, 0x80492260, 32)
        assert row[256:288] == struct.pack('>8I', 8, 1, 6, 0x12, 0x135e2580, 32, 0x492260, 32)
        assert word(row, 360) == (0x1000000 if index < 116 else 0)
        assert word(row, 684) == (1 if index < 115 else 0)
        assert word(row, 704) == (0 if index < 115 else 32)
    assert word(rows[117], 1200) == 0


check(events)
mutants = 0
for index in range(93, 118):
    for offset in range(0, 1280, 4):
        changed = list(events)
        row = bytearray(changed[index])
        row[offset] ^= 1
        changed[index] = row
        try:
            check(changed)
        except (AssertionError, KeyError):
            mutants += 1
assert mutants == 392, mutants
for a, b in [(99, 102), (105, 109), (109, 112), (106, 113), (114, 115)]:
    changed = list(events)
    changed[a], changed[b] = changed[b], changed[a]
    try:
        check(changed)
    except AssertionError:
        pass
    else:
        raise AssertionError('Concurrent request/reply/callback order mutation accepted')
(output / 'events-comparison.json').write_text(json.dumps({
    'result': 'ORIGINAL_CONCURRENT_DI86_INQUIRY_ES_WAIT_REPLY_CALLBACK_PASS',
    'verifierSha256': sha(Path(__file__)), 'generationSha256': sha(generation_path),
    'captureSha256': sha(capture_path), 'controlCaptureSha256': sha(control_path),
    'eventCount': 118, 'fieldMutantsRejected': mutants, 'orderMutantsRejected': 5,
    'replyOrder': ['DI86', 'ES_OPEN', 'DI_INQUIRY'],
    'limits': generation['limits'] + [
        'Original Wii DOL executed in Dolphin LAB; metadata is not physical Wii drive identity.',
        'All16 control records/full files/inquiry unchanged; observer timing is not cycle equivalence.',
        'Native burst delivery is still unimplemented/unverified; no first screen claimed.']}, indent=2) + '\n')
print(f'PASS118 events/nine replays/256 stride/all16 endpoints; {mutants} field mutations and five order mutations rejected')

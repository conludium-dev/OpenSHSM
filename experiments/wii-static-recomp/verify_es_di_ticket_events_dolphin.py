"""Verify original ticket reply precedes inquiry completion in the four-request chain."""
from pathlib import Path
import base64
import struct
import json
from collections import Counter

parent = Path('experiments/wii-static-recomp/verify_di_burst_events_dolphin.py')
body = parent.read_text().split("for key in ('data'", 1)[0]
for old, new in [('dolphin-di-burst-events', 'dolphin-es-di-ticket-events'),
    ("dolphin-di-burst'", "dolphin-es-di-ticket'"),
    ('verify_di_burst_dolphin.py', 'verify_es_di_ticket_dolphin.py'),
    ('build_di_burst_events_dolphin.py', 'build_es_di_ticket_events_dolphin.py'),
    ('run_di_burst_events_disc_dolphin.ps1', 'run_es_di_ticket_events_disc_dolphin.ps1'),
    ('prepare_di_burst_events_disc.py', 'prepare_es_di_ticket_events_disc.py')]:
    body = body.replace(old, new)
body = body.replace("exec(compile(body, str(parent), 'exec'), globals())",
    "body = body.replace(\"len(generation['patches']) == 9\", \"len(generation['patches']) == 10\").replace('0xc06e0000', '0xc0740000').replace('0xc06e0040', '0xc0740040')\nexec(compile(body, str(parent), 'exec'), globals())")
exec(compile(body, str(parent), 'exec'), globals())
assert generation['ticketEventsParentSha256'] == sha(experiment / 'build_di_burst_events_dolphin.py')
assert generation['eventAddress'] == 0x80740000
assert all(not layout[36 + i] or layout[18 + i] + layout[36 + i] <= 0x806f4000 or layout[18 + i] >= 0x806f4240 or
    (layout[18 + i], layout[36 + i]) == (0x806f4000, 0x240) for i in range(18))
for key in ('data', 'confPhysical', 'productPhysical', 'inquiryPhysical', 'ticketViewPhysical', 'ticketScalarsPhysical'):
    assert base64.b64decode(capture[key]) == base64.b64decode(control[key])
raw = base64.b64decode(capture['events'])
assert len(raw) == 0x50040 and raw[:16] == b'OSHSM_SC_EVENTS1'
assert struct.unpack_from('>2I', raw, 16) == (126, 0)
events = [raw[64 + i * 1280:64 + (i + 1) * 1280] for i in range(126)]
assert Counter(struct.unpack_from('>I', row)[0] for row in events) == {1: 96, 8: 10, 9: 10, 5: 2, 4: 1, 2: 2, 3: 2, 13: 1, 6: 1, 7: 1}
sites = {patch['kind']: patch['address'] for patch in generation['patches']}


def word(row, offset):
    return struct.unpack_from('>I', row, offset)[0]


def check(rows):
    for row in rows:
        assert word(row, 4) == sites[word(row, 0)]
    for index, kind, lr, msr, r3, r4 in [
        (112, 1, 0x80242384, 0x2032, 0, 0x135e0080),
        (113, 1, 0x802423cc, 0x2032, 1, 0x31),
        (114, 8, 0x802423dc, 0x2032, 0x935e00ac, 0x31),
        (116, 1, 0x80241f68, 0x30, 1, 0x32),
        (117, 1, 0x80241cec, 0x30, 1, 0x34),
        (118, 1, 0x80241ecc, 0x30, 1, 0x38),
        (119, 13, 0x80249a90, 0x2032, 0, 0x2032),
        (120, 1, 0x80241cec, 0x30, 1, 0x34),
        (121, 2, 0x80241e8c, 0x32, 1, 0x804983c0),
        (122, 6, 0x80225930, 0x32, 1, 0x804983c0),
        (123, 7, 0x802236f0, 0x32, 32, 0x80492280),
        (124, 3, 0x80225930, 0x32, 0, 0x32)]:
        row = rows[index]
        assert (word(row, 0), word(row, 12), word(row, 16), word(row, 24), word(row, 28)) == (kind, lr, msr, r3, r4)
    request = struct.pack('>8I', 7, 1, 4, 0x1b, 1, 1, 0x53ffb0, 0)
    assert rows[112][64:128] == rows[112][128:192] == request + bytes(32)
    assert word(rows[117], 32) == 0x935e0080 and word(rows[120], 32) == 0x935e00e0
    assert word(rows[115], 1188) == 0x935e00ac and word(rows[115], 1184) == 0x40001
    for index in (118, 119):
        assert rows[index][64:128] == struct.pack('>8I', 8, 0, 7, 0x1b, 1, 1, 0x8053ffb0, 0) + bytes(32)
        assert rows[index][128:192] == struct.pack('>8I', 8, 0, 7, 0x1b, 1, 1, 0x53ffb0, 0) + bytes(32)
    assert word(rows[118], 36) == 0x935e0120 and word(rows[119], 36) == 0x935e0060
    assert word(rows[119], 1188) == 0 and word(rows[119], 1184) == 0x20001
    for index in (121, 122, 123, 124):
        assert word(rows[index], 360) == (0x1000000 if index < 124 else 0)
        assert word(rows[index], 684) == (1 if index < 123 else 0)
        assert word(rows[index], 704) == (0 if index < 123 else 32)


check(events)
mutants = 0
for index in range(112, 126):
    for offset in range(0, 1280, 4):
        changed = list(events)
        row = bytearray(changed[index])
        row[offset] ^= 1
        changed[index] = row
        try:
            check(changed)
        except (AssertionError, KeyError):
            mutants += 1
assert mutants == 192, mutants
for a, b in [(112, 113), (117, 120), (118, 119), (119, 123), (121, 122)]:
    changed = list(events)
    changed[a], changed[b] = changed[b], changed[a]
    try:
        check(changed)
    except AssertionError:
        pass
    else:
        raise AssertionError('Ticket/inquiry order mutation accepted')
(output / 'events-comparison.json').write_text(json.dumps({'result': 'ORIGINAL_FOUR_REQUESTS_TICKET_REPLY_RETURN_BEFORE_INQUIRY_COMPLETION_PASS',
    'verifierSha256': sha(Path(__file__)), 'captureSha256': sha(capture_path), 'generationSha256': sha(generation_path),
    'fieldMutantsRejected': mutants, 'orderMutantsRejected': 5, 'limits': generation['limits'] + [
        'All16 control records/full files/full216 ticket and scalars unchanged by observers.',
        'Reply order86→ES OPEN→ES ticket1B→DI inquiry12 observed; ticket API0/2032 before inquiry callbacks.',
        'Original vector53FFB0 vs native53FF10 is explicit caller-stack relocation, not byte-equal request claim.',
        'Dolphin LAB/interpreter timing, not physical Wii/cycles or complete native pipeline.']}, indent=2) + '\n')
print(f'PASS126events/tenreplays/all256stride/all16controls;{mutants} field and five order mutations; ticket reply BEFORE inquiry')

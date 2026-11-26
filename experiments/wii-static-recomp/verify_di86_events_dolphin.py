"""Verify original DI86 actual IOS reply, API-before-ACK and callback state lifetime."""
from pathlib import Path
import base64
import json
import struct
from collections import Counter

parent = Path('experiments/wii-static-recomp/verify_di_events_dolphin.py')
body = parent.read_text().split("assert base64.b64decode(capture['data'])", 1)[0]
body = body.replace('dolphin-di-events', 'dolphin-di86-events').replace('dolphin-di-initialized', 'dolphin-di86').replace(
    'verify_di_initialized_dolphin.py', 'verify_di86_dolphin.py').replace(
    'build_di_events_dolphin.py', 'build_di86_events_dolphin.py').replace(
    'run_di_events_disc_dolphin.ps1', 'run_di86_events_disc_dolphin.ps1').replace(
    'prepare_di_events_disc.py', 'prepare_di86_events_disc.py').replace(
    "len(generation['patches']) == 2", "len(generation['patches']) == 4").replace(
    '(1216, 0x935e25c0), (1248, 0x935e2540)', '(1216, 0x8052ac78), (1248, 0x935e2560)')
exec(compile(body, str(parent), 'exec'), globals())
for patch in generation['patches']:
    span = words_at(patch['trampoline'], (patch['end'] - patch['trampoline']) // 4)
    expected = [0x3d808049, 0x618c83a0]
    for byte in range(0, 320, 4):
        expected.extend([0x800c0000 | byte, 0x900b0000 | (320 + byte)])
    assert sum(span[i:i + len(expected)] == expected for i in range(len(span) - len(expected) + 1)) == 1
assert base64.b64decode(capture['data']) == base64.b64decode(control['data'])
for key in ('confPhysical', 'productPhysical'):
    assert base64.b64decode(capture[key]) == base64.b64decode(control[key])
raw = base64.b64decode(capture['events'])
assert len(raw) == 0x50040 and raw[:16] == b'OSHSM_SC_EVENTS1'
assert struct.unpack_from('>2I', raw, 16) == (84, 0)
events = [raw[64 + i * 1280:64 + (i + 1) * 1280] for i in range(84)]
assert Counter(struct.unpack_from('>I', row)[0] for row in events) == {1: 81, 2: 1, 3: 1, 4: 1}
assert [(i, struct.unpack_from('>I', row)[0]) for i, row in enumerate(events) if struct.unpack_from('>I', row)[0] != 1] == [(78, 4), (81, 2), (82, 3)]


def check(row, index):
    kind, site = (4, 0x80227f20) if index == 78 else (2, 0x802258a0) if index == 81 else (3, 0x80225940) if index == 82 else (1, 0x80241c30)
    assert struct.unpack_from('>2I', row) == (kind, site)
    msr = 0xa032 if index == 78 else 0x32 if index >= 81 else 0x2032 if index == 76 else 0x30
    assert struct.unpack_from('>I', row, 16)[0] == msr
    assert struct.unpack_from('>2I', row, 24) == ((0, 0x135e0080) if index == 76 else (1, 0x2032) if index == 78 else (1, 0x804983a0) if index in (81, 82) else (1, 0x38))
    reply = index >= 81
    header = struct.pack('>8I', *( [8, 1, 6, 0x86, 0x135e2560, 32, 0, 0] if reply else [6, 3, 3, 0x86, 0x135e2560, 32, 0, 0]))
    tail = struct.pack('>2I', 0x802258a0, 0x804983a0) + bytes(24)
    assert row[64:128] == header + tail and row[128:192] == header + bytes(32)
    assert row[1248:1280] == b'\x86' + bytes(31)
    cleared = index >= 82
    assert row[320:352] == struct.pack('>4I', 0, 1, 0 if cleared else 0x01000000, 0xfeebdaed) + bytes(16)
    assert row[1216:1248] == struct.pack('>8I', 0 if cleared else 0x01000000, 1, 1, 0x01010000, 0, 0, 0x935e25c0, 0x935e2540)
    assert struct.unpack_from('>I', row, 36)[0] == (0x935e0060 if index == 83 else 0x935e00c0)
    return {'event': index, 'kind': kind, 'MSR': msr, 'cachedPacketHex': row[64:128].hex(),
        'physicalPacketHex': row[128:192].hex(), 'stateHex': row[320:352].hex()}


cases = [check(events[i], i) for i in (76, 78, 81, 82, 83)]
locations = [0, 4, 16, 24, 28, 36, 64, 68, 72, 76, 80, 84, 96, 100, 128, 132, 136,
    320, 324, 328, 332, 1216, 1220, 1224, 1248, 1252]
for index in (81, 82):
    for location in locations:
        changed = bytearray(events[index])
        changed[location] ^= 1
        try:
            check(changed, index)
        except AssertionError:
            pass
        else:
            raise AssertionError('DI86 reply/callback/state/command mutant accepted')
native_path = root / 'mass-di86-inputs-observer/observation.json'
native = json.loads(native_path.read_text())
assert sha(native_path.with_name('observation.log')) == native['logSha256']
for tag, expected in [('DI86_PACKET_CACHED', events[76][64:128]), ('DI86_PACKET_PHYSICAL', events[76][128:192]),
    ('DI86_COMMAND_CACHED', events[76][1248:1280]), ('DI86_COMMAND_PHYSICAL', events[76][1248:1280]),
    ('DI86_CALLBACK_STATE', events[76][320:352]), ('DI86_CONTROL', events[76][1216:1248])]:
    line = next(line for line in native['observations'] if line.startswith(tag + ' '))
    assert bytes(map(int, line.split()[1:]))[:len(expected)] == expected
(output / 'events-comparison.json').write_text(json.dumps({'result': 'ORIGINAL_DI86_IOS_REPLY1_CALLBACK32_STATE_CLEAR_API_BEFORE_ACK_PASS',
    'verifierSha256': sha(Path(__file__)), 'generationSha256': sha(generation_path), 'captureSha256': sha(capture_path),
    'controlCaptureSha256': sha(control_path), 'nativeInputsSha256': sha(native_path), 'cases': cases,
    'mutantsRejected': len(locations) * 2, 'limits': generation['limits'] + [
        'All16 control records/full files unchanged; original reply1 and SDK callback MSR32 now measured, not assumed.',
        'Observer EE/scratch/timing perturbations and lab bootstrap retained; not physical-drive or cycle equivalence.']}, indent=2) + '\n')
print('PASS84events/four replay sites/256stride/all16 control records identical/IOSreply1-callback32-busy/pending clear/APIbeforeACK;52mutants/native prepared matches')

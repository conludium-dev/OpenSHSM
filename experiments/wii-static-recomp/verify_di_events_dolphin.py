"""Verify replay observers and measured original DI packet/global transitions."""
from pathlib import Path
import base64
import hashlib
import json
import struct
from collections import Counter

parent = Path('experiments/wii-static-recomp/verify_sysconf_events.py')
body = parent.read_text().split('\ndata, golden =', 1)[0]
body = body.replace('verify_sysconf_chain.py', 'verify_di_initialized_dolphin.py').replace(
    'dolphin-sysconf-events-fixed', 'dolphin-di-events').replace(
    'dolphin-sysconf-long', 'dolphin-di-initialized').replace(
    'build_sysconf_events_dolphin.py', 'build_di_events_dolphin.py').replace(
    'run_sysconf_events_fixed_disc_dolphin.ps1', 'run_di_events_disc_dolphin.ps1').replace(
    'prepare_sysconf_events_fixed_disc.py', 'prepare_di_events_disc.py').replace(
    "len(generation['patches']) == 9", "len(generation['patches']) == 2")
exec(compile(body, str(parent), 'exec'), globals())
assert generation['eventsParentGeneratorSha256'] == sha(experiment / 'build_sysconf_events_dolphin.py')
for patch in generation['patches']:
    span = words_at(patch['trampoline'], (patch['end'] - patch['trampoline']) // 4)
    for slot, address in [(1168, 0x8052afc4), (1172, 0x8052afc8), (1176, 0x8052afe4),
        (1180, 0x80528a38), (1184, 0x8052ab10), (1188, 0x80528a98),
        (1192, 0x8052ac90), (1196, 0x8052ac94), (1200, 0x8052ac84),
        (1204, 0x8052ac80), (1208, 0x8052afc0), (1212, 0x80528b74)]:
        expected = [0x3d800000 | (address >> 16), 0x618c0000 | (address & 65535), 0x800c0000, 0x900b0000 | slot]
        assert sum(span[i:i + 4] == expected for i in range(len(span) - 3)) == 1
    for slot, address in [(1216, 0x935e25c0), (1248, 0x935e2540)]:
        expected = [0x3d800000 | (address >> 16), 0x618c0000 | (address & 65535)]
        for byte in range(0, 32, 4):
            expected.extend([0x800c0000 | byte, 0x900b0000 | (slot + byte)])
        assert sum(span[i:i + len(expected)] == expected for i in range(len(span) - len(expected) + 1)) == 1
assert base64.b64decode(capture['data']) == base64.b64decode(control['data'])
assert base64.b64decode(capture['confPhysical']) == base64.b64decode(control['confPhysical'])
assert base64.b64decode(capture['productPhysical']) == base64.b64decode(control['productPhysical'])
raw = base64.b64decode(capture['events'])
assert len(raw) == 0x50040 and raw[:16] == b'OSHSM_SC_EVENTS1'
count, overflow = struct.unpack_from('>2I', raw, 16)
assert (count, overflow) == (83, 0)
events = [raw[64 + i * 1280:64 + (i + 1) * 1280] for i in range(count)]
assert Counter(struct.unpack_from('>I', row)[0] for row in events) == {1: 81, 2: 2}
assert [i for i, row in enumerate(events) if struct.unpack_from('>I', row)[0] == 2] == [76, 82]


def check(row, index):
    returning = index in (76, 82)
    second = index in (77, 82)
    assert struct.unpack_from('>2I', row) == ((2, 0x80225cbc) if returning else (1, 0x80241c30))
    assert struct.unpack_from('>I', row, 16)[0] == (0xa032 if returning else 0x2032)
    assert struct.unpack_from('>2I', row, 24) == ((1, 0x2032) if returning else (0, 0x135e0080))
    descriptor = (4 if second else 3) if returning else (3 if second else 0xffffffff)
    fields = list(struct.unpack_from('>12I', row, 1168))
    assert fields == [0x935e25e0, 0x93600000, 1, 0x935e0000, 0x93600000, descriptor,
        0x935e25c0, 0x935e2540, 0x01010000, 0, 0x01000000, 0]
    head = [8, descriptor, 1, 0x135e25c0, 0, 1, 0x8053ff90, 0] if returning else [
        1, 3 if second else 0x100, 0, 0x135e25c0, 0, 1, 0x8053ff90, 0]
    packet = struct.pack('>8I', *head) + bytes(32)
    assert row[64:128] == row[128:192] == packet
    assert row[1216:1248] == b'/dev/di\0' + bytes(24)
    assert struct.unpack_from('>I', row, 36)[0] == (0x935e0060 if returning else 0x935e00c0)
    assert struct.unpack_from('>2I', row, 52) == ((17, 17) if index == 82 else (16, 16) if index == 76 else (16, 17) if second else (15, 16))
    return {'event': index, 'fields': fields, 'packetHex': packet.hex(), 'returning': returning}


cases = [check(events[i], i) for i in (71, 76, 77, 82)]
native = root / 'mass-sysconf-complete-boot'
native_build = json.loads((native / 'build.json').read_text())
for path, digest in {**native_build['sourceHashes'], **native_build['headerHashes']}.items():
    assert sha(Path(path)) == digest
for row in native_build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
native_log = native / 'live-boot.log'
native_lines = native_log.read_text().splitlines()
packet_line = next(line for line in native_lines if line.startswith('SC_COMPLETE_NEXT_PACKET '))
path_line = next(line for line in native_lines if line.startswith('SC_COMPLETE_NEXT_PATH '))
native_packet = bytes(map(int, packet_line.split()[1:]))
native_path = bytes(map(int, path_line.split()[1:]))
original_packet = bytearray(events[71][128:192])
assert struct.unpack_from('>I', original_packet, 24)[0] == 0x8053ff90
struct.pack_into('>I', original_packet, 24, 0x80540010)
assert native_packet == original_packet
assert native_path == events[71][1216:1248] + bytes(32)
assert any('BOOT_BOUNDARY pc=80241c30 lr=80242384 msr=2032' in line for line in native_lines)
locations = [0, 4, 16, 24, 28, 36, 52, 56, 64, 68, 72, 76, 88, 128, 132, 1168, 1172,
    1176, 1180, 1184, 1188, 1192, 1196, 1200, 1204, 1208, 1212, 1216]
for location in locations:
    changed = bytearray(events[76])
    changed[location] ^= 1
    try:
        check(changed, 76)
    except AssertionError:
        pass
    else:
        raise AssertionError('DI packet/global/heap/queue mutation accepted')
(output / 'events-comparison.json').write_text(json.dumps({'result': 'ORIGINAL_DI_TWO_OPEN_PACKETS_GLOBALS_ENDPOINTS_PASS',
    'verifierSha256': sha(Path(__file__)), 'parentVerifierSha256': sha(parent),
    'generationSha256': sha(generation_path), 'captureSha256': sha(capture_path),
    'controlCaptureSha256': sha(control_path), 'eventCount': count, 'cases': cases,
    'nativePreparedPacket': {'buildSha256': sha(native / 'build.json'), 'logSha256': sha(native_log),
        'ignoredPointerRelocation': ['8053ff90', '80540010'],
        'scope': 'Retained unchanged native profile, physical prepared64/path64 BEFORE DI submission; not native OPEN execution.'},
    'mutantsRejected': len(locations), 'limits': generation['limits'] + [
        'All16 control records and physical files byte-identical. EE masking/scratch reads/timing perturbations disclosed, not physical-cycle evidence.',
        'Only OPEN and low-level SDK return/global state verified; DI ioctl/disc reads unverified.']}, indent=2) + '\n')
print('PASS83events/two replay sites/256stride checks/all16 endpoints identical/DI packets64x2-globals-FDs3-4;28mutants')

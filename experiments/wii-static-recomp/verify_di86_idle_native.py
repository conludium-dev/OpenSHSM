"""Validate the actual three-request native wait topology, not a relaxed idle guard."""
from pathlib import Path
import base64
import hashlib
import json
import struct

root = Path('work/private-game/static-recomp')
output = root / 'mass-di86-idle-observer'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = json.loads((output / 'observation.json').read_text())
assert report['builderSha256'] == sha(Path('experiments/wii-static-recomp/observe_di86_idle_native.py'))
assert report['baseBuildSha256'] == sha(root / 'mass-di86-boot/build.json')
assert report['records'] == json.loads((root / 'mass-di86-boot/build.json').read_text())['records']
for path, digest in {**report['sourceHashes'], **report['headerHashes']}.items():
    assert sha(Path(path)) == digest
for row in report['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
assert sha(output / 'observation.log') == report['logSha256']
values = {}
for line in report['observations']:
    if line.startswith('DI86_IDLE_'):
        tag, *words = line.split()
        assert tag not in values
        values[tag] = words


def check(values):
    assert list(map(lambda word: int(word, 16), values['DI86_IDLE_DVD_GLOBALS'])) == [0xe, 0x80492280, 0, 1]
    assert bytes(map(int, values['DI86_IDLE_DVD_BLOCK']))[:48] == struct.pack(
        '>12I', 0, 0, 0xe, 1, 0, 32, 0x80492260, 32, 0, 0, 0x80211060, 0)
    assert list(map(lambda word: int(word, 16), values['DI86_IDLE_STATE'])) == [
        0x8032, 0, 0x80492658, 0x80492a70, 0x492a70, 0, 1, 0, 0, 16, 18, 16, 0xffffffff, 0x935e016c, 0, 0, 4]
    assert list(map(lambda word: int(word, 16), values['DI86_IDLE_IPC'])) == [0x32, 0x135e0080, 0x135e0080, 0, 0]
    packet = bytes(map(int, values['DI86_IDLE_PACKET']))
    queued = bytes(map(int, values['DI86_IDLE_QUEUED_PACKET']))
    waiting = bytes(map(int, values['DI86_IDLE_WAIT_PACKET']))
    assert packet == struct.pack('>10I', 6, 3, 3, 0x86, 0x135e2560, 32, 0, 0, 0x802258a0, 0x804983a0) + bytes(24)
    assert queued == struct.pack('>10I', 6, 0, 3, 0x12, 0x135e2580, 32, 0x492260, 32, 0x802258a0, 0x804983c0) + bytes(24)
    expected = bytearray(64)
    struct.pack_into('>8I', expected, 0, 1, 0, 0, 0x528cf0, 0, 0, 0, 0)
    struct.pack_into('>2I', expected, 44, 0x80492658, 0x80492658)
    assert waiting == expected
    thread = bytes(map(int, values['DI86_IDLE_THREAD']))
    assert len(thread) == 64 and struct.unpack_from('>H', thread)[0] == 4
    assert struct.unpack_from('>I', thread, 20)[0] == 0x935e016c
    assert thread[24:32] == bytes(8)
    callback = bytes(map(int, values['DI86_IDLE_CALLBACK']))
    assert callback == struct.pack('>4I', 0, 1, 0x01000000, 0xfeebdaed) + bytes(16) + struct.pack(
        '>8I', 0x80222f80, 1, 0x01000000, 0xfeebdaed, 1, 0, 0, 0)
    assert bytes(map(int, values['DI86_IDLE_ES_PATH']))[:8] == b'/dev/es\0'
    commands = bytes(map(int, values['DI86_IDLE_COMMAND_RING']))
    assert commands == bytes(32) + b'\x86' + bytes(31) + b'\x12' + bytes(63)
    queue = bytes(map(int, values['DI86_IDLE_REQUEST_QUEUE']))
    assert len(queue) == 80
    assert struct.unpack_from('>6I', queue) == (16, 18, 0, 2, 0x935e00e0, 0x935e0140)


check(values)
mutants = 0
for tag, words in values.items():
    if tag == 'DI86_IDLE_THREAD':
        locations = [0, 1, 20, 24, 28]
    elif tag == 'DI86_IDLE_REQUEST_QUEUE':
        locations = [0, 4, 8, 12, 16, 20]
    elif tag == 'DI86_IDLE_ES_PATH':
        locations = list(range(8))
    elif tag == 'DI86_IDLE_DVD_BLOCK':
        locations = list(range(48))
    else:
        locations = list(range(len(words)))
    for location in locations:
        changed = {key: list(value) for key, value in values.items()}
        base = 16 if tag in ('DI86_IDLE_STATE', 'DI86_IDLE_IPC', 'DI86_IDLE_DVD_GLOBALS') else 10
        changed[tag][location] = format(int(words[location], base) ^ 1, 'x') if base == 16 else str(int(words[location]) ^ 1)
        try:
            check(changed)
        except AssertionError:
            mutants += 1
        else:
            raise AssertionError('Wrong async/sync wait topology accepted: ' + tag)
(output / 'comparison.json').write_text(json.dumps({'result': 'NATIVE_DI86_SENT_INQUIRY_QUEUED_ES_OPEN_WAIT_TOPOLOGY_PASS',
    'verifierSha256': sha(Path(__file__)), 'observationSha256': sha(output / 'observation.json'), 'mutantsRejected': mutants,
    'limits': ['Read-only stopped native topology, not original three-request response/callback proof.',
        'Main sleeps on queued ES OPEN0140+44, not DI86; inquiry12 is also queued. No guard relaxed or fake inquiry supplied.']}, indent=2) + '\n')
print('PASS actual DI86 sent0080/inquiry12 queued00E0/ES OPEN queued0140/main wait016C/two queued requests; ' + str(mutants) + 'mutants; ALL125 unchanged')

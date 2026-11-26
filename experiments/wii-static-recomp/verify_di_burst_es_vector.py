"""Validate stopped native ticket-view request; no ES response is inferred."""
from pathlib import Path
import hashlib
import json
import struct

root = Path('work/private-game/static-recomp')
output = root / 'mass-di-burst-es-vector-observer'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = json.loads((output / 'observation.json').read_text())
assert report['builderSha256'] == sha(Path('experiments/wii-static-recomp/observe_di_burst_es_vector.py'))
assert report['baseBuildSha256'] == sha(root / 'mass-di-burst-cache-boot/build.json')
assert report['records'] == json.loads((root / 'mass-di-burst-cache-boot/build.json').read_text())['records']
for path, digest in {**report['sourceHashes'], **report['headerHashes']}.items():
    assert sha(Path(path)) == digest
for row in report['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
assert sha(output / 'observation.log') == report['logSha256']
values = {}
for line in report['observations']:
    if line.startswith('ES_BURST_'):
        tag, *words = line.split()
        if tag in ('ES_BURST_VECTOR_INFO', 'ES_BURST_DATA_CACHED', 'ES_BURST_DATA_PHYSICAL'):
            tag += '_' + words.pop(0)
        assert tag not in values
        values[tag] = words


def check(data):
    for tag, expected in [
        ('ES_BURST_ARGUMENTS', [0x8053fdd0, 0x80540060, 7, 0x8053ff10, 8, 0, 0x935e0080, 0x8053ff10, 0]),
        ('ES_BURST_LAYOUT', [4, 0x935e0120, 18, 18, 2, 2, 0, 14, 0x80492280, 0x38, 0x135e0140, 0x135e0140]),
        ('ES_BURST_VECTOR_INFO_0', [0, 0]), ('ES_BURST_VECTOR_INFO_1', [0x8053ff80, 216])]:
        assert [int(word, 16) for word in data[tag]] == expected
    for tag, packet in [
        ('ES_BURST_PACKET_CACHED', [7, 1, 4, 27, 1, 1, 0x8053ff10, 0]),
        ('ES_BURST_PACKET_PHYSICAL', [8, 1, 6, 0x86, 0x135e2560, 32, 0, 0])]:
        assert bytes(map(int, data[tag])) == struct.pack('>8I', *packet) + bytes(32)
    assert bytes(map(int, data['ES_BURST_VECTOR_CACHED']))[:16] == struct.pack('>4I', 0, 0, 0x8053ff80, 216)
    assert bytes(map(int, data['ES_BURST_VECTOR_PHYSICAL']))[:16] == bytes(16)
    assert bytes(map(int, data['ES_BURST_INQUIRY_PACKET'])) == struct.pack(
        '>10I', 6, 0, 3, 18, 0x135e2580, 32, 0x492260, 32, 0x802258a0, 0x804983c0) + bytes(24)
    assert len(data['ES_BURST_DATA_CACHED_1']) == 216
    assert data['ES_BURST_DATA_CACHED_1'] == data['ES_BURST_DATA_PHYSICAL_1']


check(values)
mutants = 0
for tag, words in values.items():
    locations = range(16) if tag.startswith('ES_BURST_VECTOR_') and 'INFO' not in tag else range(len(words))
    for offset in locations:
        changed = {key: list(value) for key, value in values.items()}
        hexadecimal = tag in ('ES_BURST_ARGUMENTS', 'ES_BURST_LAYOUT', 'ES_BURST_VECTOR_INFO_0', 'ES_BURST_VECTOR_INFO_1')
        altered = int(words[offset], 16 if hexadecimal else 10) ^ 1
        changed[tag][offset] = format(altered, 'x') if hexadecimal else str(altered)
        try:
            check(changed)
        except AssertionError:
            mutants += 1
        else:
            raise AssertionError('Native ES vector mutant accepted: ' + tag)
(output / 'comparison.json').write_text(json.dumps({'result': 'NATIVE_POST_BURST_ES_DI_TICKET_VIEW_PRE_FLUSH_PASS',
    'verifierSha256': sha(Path(__file__)), 'observationSha256': sha(output / 'observation.json'),
    'mutantsRejected': mutants, 'limits': ['All125 PPC objects unchanged; observation is before flush syscall/vector normalization/submission.',
        'Zero-length NULL input is real SDK shape, output216 currently stale stack, NOT ticket data or IOS response.',
        'Cached packet newly7/FD4/1B, physical packet still old86reply; no premature coherency normalization.',
        'Inquiry12 remains unfinished; original ticket-view service response not yet captured.']}, indent=2) + '\n')
print(f'PASS actual ES1B/null-input/output216/cache-vs-physical/FIFO/unfinishedInquiry;{mutants} mutations rejected; ALL125 unchanged')

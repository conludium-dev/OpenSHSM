"""Verify the actual pending ES16 vectors; do not infer a service response."""
from pathlib import Path
import hashlib
import json
import struct

root = Path('work/private-game/static-recomp')
output = root / 'mass-di-inquiry-es-vector-observer'
base = root / 'mass-di-inquiry-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = json.loads((output / 'observation.json').read_text())
assert report['builderSha256'] == sha(Path('experiments/wii-static-recomp/observe_di_inquiry_es_vector.py'))
assert report['baseBuildSha256'] == sha(base / 'build.json')
assert report['records'] == json.loads((base / 'build.json').read_text())['records']
for path, digest in {**report['sourceHashes'], **report['headerHashes']}.items():
    assert sha(Path(path)) == digest
for row in report['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
assert sha(output / 'es-vector-observer') == report['executableSha256']
assert sha(output / 'observation.log') == report['logSha256']
values = {}
for line in report['observations']:
    if line.startswith('ES_BURST_'):
        tag, *words = line.split()
        if tag in ('ES_BURST_VECTOR_INFO', 'ES_BURST_DATA_CACHED', 'ES_BURST_DATA_PHYSICAL'):
            tag += '_' + words.pop(0)
        assert tag not in values
        values[tag] = words
ticket_id = (Path('work/private-game/disc/DATA/ticket.bin').read_bytes())[0x1d0:0x1d8]

def check(data):
    for tag, expected in [
        ('ES_BURST_ARGUMENTS', [0x8053fc30, 0x8053fce0, 1, 0x8053fd70, 8, 8, 0x935e0080, 0x8053fd70, 0]),
        ('ES_BURST_LAYOUT', [4, 0x935e00c0, 19, 19, 3, 3, 0, 14, 0, 0x38, 0x135e0080, 0x135e00e0]),
        ('ES_BURST_VECTOR_INFO_0', [0x8053fca0, 8]), ('ES_BURST_VECTOR_INFO_1', [0, 0]),
        ('ES_BURST_VECTOR_INFO_2', [0x8053fcc0, 4])]:
        assert [int(word, 16) for word in data[tag]] == expected
    for tag, packet in [
        ('ES_BURST_PACKET_CACHED', [7, 0, 4, 22, 1, 2, 0x8053fd70, 0]),
        ('ES_BURST_PACKET_PHYSICAL', [8, 0, 7, 27, 1, 1, 0x53ff10, 0])]:
        assert bytes(map(int, data[tag])) == struct.pack('>8I', *packet) + bytes(32)
    assert bytes(map(int, data['ES_BURST_VECTOR_CACHED']))[:24] == struct.pack('>6I', 0x8053fca0, 8, 0, 0, 0x8053fcc0, 4)
    assert bytes(map(int, data['ES_BURST_DATA_CACHED_0'])) == ticket_id
    assert bytes(map(int, data['ES_BURST_DATA_PHYSICAL_0'])) == struct.pack('>2I', 0x8053fcc0, 0x801a1d5c)
    for cache in ('CACHED', 'PHYSICAL'):
        assert bytes(map(int, data['ES_BURST_DATA_' + cache + '_2'])) == struct.pack('>I', 0x8053fcf0)
    assert bytes(map(int, data['ES_BURST_INQUIRY_PACKET'])) == struct.pack('>10I',
        8, 1, 6, 18, 0x135e2580, 32, 0x80492260, 32, 0x802258a0, 0x804983c0) + bytes(24)

check(values)
mutants = 0
for tag, words in values.items():
    if tag == 'ES_BURST_VECTOR_PHYSICAL':
        continue
    locations = range(24) if tag == 'ES_BURST_VECTOR_CACHED' else range(len(words))
    for offset in locations:
        changed = {key: list(value) for key, value in values.items()}
        hexadecimal = tag in ('ES_BURST_ARGUMENTS', 'ES_BURST_LAYOUT') or tag.startswith('ES_BURST_VECTOR_INFO_')
        altered = int(words[offset], 16 if hexadecimal else 10) ^ 1
        changed[tag][offset] = format(altered, 'x') if hexadecimal else str(altered)
        try:
            check(changed)
        except AssertionError:
            mutants += 1
        else:
            raise AssertionError('Checked ES16 field mutation accepted: ' + tag)
(output / 'comparison.json').write_text(json.dumps({'result': 'NATIVE_PENDING_ES16_TICKET_ID_NULL_ARRAY_COUNT4_PASS',
    'verifierSha256': sha(Path(__file__)), 'observationSha256': sha(output / 'observation.json'),
    'mutantsRejected': mutants, 'limits': ['All125 PPC objects unchanged; stopped before ES16 flush/submission.',
        'Input matches ticket ID, NOT title ID. Output count contains stale stack, not a reply.',
        'Physical vector and cached trailing40 bytes are recorded but not semantically validated.',
        'Dolphin upstream GetConsumption is a stub; no physical IOS equivalence or automatic success inferred.']}, indent=2) + '\n')
print(f'PASS pending ES16 actual ticketID8/null-array/count4/source-retired inquiry; {mutants} checked mutations rejected; ALL125 unchanged')

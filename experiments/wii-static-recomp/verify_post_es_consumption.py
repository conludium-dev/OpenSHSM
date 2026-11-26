"""Validate actual native CLOSE packet before submission, not an IOS response."""
from pathlib import Path
import hashlib
import json
import struct

root = Path('work/private-game/static-recomp')
output = root / 'mass-post-es-consumption-observer'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = json.loads((output / 'observation.json').read_text())
assert report['builderSha256'] == sha(Path('experiments/wii-static-recomp/observe_post_es_consumption.py'))
assert report['baseBuildSha256'] == sha(root / 'mass-es-consumption-boot/build.json')
assert report['records'] == json.loads((root / 'mass-es-consumption-boot/build.json').read_text())['records']
for path, digest in {**report['sourceHashes'], **report['headerHashes']}.items():
    assert sha(Path(path)) == digest
for row in report['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
assert sha(output / 'es-vector-observer') == report['executableSha256']
assert sha(output / 'observation.log') == report['logSha256']
values = {}
for line in report['observations']:
    if line.startswith('ES_NEXT_'):
        tag, *words = line.split()
        assert tag not in values
        values[tag] = words
expected_packet = struct.pack('>8I', 2, 0, 4, 0x16, 1, 2, 0x8053fd70, 0) + bytes(32)

def check(data):
    assert [int(value, 16) for value in data['ES_NEXT_ARGUMENTS']] == [
        0x8053fef0, 0xcd000000, 0x135e0080, 0x804b2bc0, 0x804b2c40, 0, 1, 0]
    for cache in ('CACHED', 'PHYSICAL'):
        assert bytes(map(int, data['ES_NEXT_PACKET_' + cache])) == expected_packet

check(values)
mutants = 0
for tag, words in values.items():
    for index, value in enumerate(words):
        bad = {name: list(items) for name, items in values.items()}
        hexadecimal = tag == 'ES_NEXT_ARGUMENTS'
        changed = int(value, 16 if hexadecimal else 10) ^ 1
        bad[tag][index] = format(changed, 'x') if hexadecimal else str(changed)
        try:
            check(bad)
        except AssertionError:
            mutants += 1
        else:
            raise AssertionError('Pending CLOSE mutation accepted')
assert mutants == 136
(output / 'comparison.json').write_text(json.dumps({'result': 'NATIVE_ES_CLOSE_FD4_COHERENT64_REUSED_IGNORED_FIELDS_PASS',
    'verifierSha256': sha(Path(__file__)), 'observationSha256': sha(output / 'observation.json'),
    'mutantsRejected': mutants, 'limits': ['All125 original PPC objects unchanged, readonly diagnostic.',
        'Command2/FD4 is CLOSE; retained16/1/2/vector8053FD70 are ignored reused fields, not another ES16 call.',
        'Physical CLOSE retains virtual ignored vector; no clearing/normalization imposed.',
        'Native request still before submission/response; original FD4 CLOSE oracle is separate.']}, indent=2) + '\n')
print('PASS native pending CLOSE2/FD4/both64coherent/ignoredES16fields preserved/136 mutations/ALL125 unchanged')

"""Prove current vector/cache observations and source contracts without granting flush permission."""
from pathlib import Path
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'mass-es-vector-observer'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = json.loads((output / 'observation.json').read_text())
assert report['builderSha256'] == sha(experiment / 'observe_es_vector_boot.py')
base = root / 'mass-es-open-boot'
assert report['baseBuildSha256'] == sha(base / 'build.json')
assert report['records'] == json.loads((base / 'build.json').read_text())['records'] and len(report['records']) == 125
for row in report['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for path, digest in {**report['sourceHashes'], **report['headerHashes']}.items():
    assert sha(Path(path)) == digest
for path, digest in report['headerHashes'].items():
    assert sha(base / Path(path).name) == digest
assert report['executableSha256'] == sha(output / 'es-vector-observer')
assert report['logSha256'] == sha(output / 'observation.log')

def check(lines):
    assert 'ES_FLUSH_ARGUMENTS 8053feb0 8053ff40 1 935e0080' in lines
    assert 'ES_VECTOR_CACHED 8053ff20 8' in lines
    assert 'ES_VECTOR_PHYSICAL 80540070 0' in lines
    for view in ('PHYSICAL', 'CACHED'):
        line = next(line for line in lines if line.startswith('ES_OUTPUT_' + view + ' '))
        assert bytes(map(int, line.split()[1:])) == bytes(32)
    assert any(line.startswith('BOOT_BOUNDARY pc=80212ff4 lr=80242fc8 msr=a032') for line in lines)
    assert 'BOOT_STM_ASYNC dispatched=1 pending=1 6 1 324927520 4096 4796512 32 4796544 32' in lines

lines = (output / 'observation.log').read_text().splitlines()
check(lines)
for old, new in (('ES_VECTOR_CACHED 8053ff20 8', 'ES_VECTOR_CACHED 8053ff40 1'),
    ('ES_VECTOR_PHYSICAL 80540070 0', 'ES_VECTOR_PHYSICAL 8053ff20 8')):
    try:
        check([new if line == old else line for line in lines])
    except AssertionError:
        pass
    else:
        raise AssertionError('Wrong buffer/length or forced coherent vector accepted')
dol = Path('work/private-game/disc/DATA/sys/main.dol')
data = dol.read_bytes()
assert sha(dol) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
layout = struct.unpack('>64I', data[:256])
opcodes = {0x80249c84: 0x38610020, 0x80249c88: 0x38000008, 0x80249ca4: 0x4bff94ed,
    0x80249cac: 0x40820014, 0x80249cb8: 0x909f0004, 0x80249cbc: 0x901f0000, 0x80242fc4: 0x4bfd000d,
    0x80212fe4: 0x5484d97e, 0x80212fe8: 0x7c8903a6, 0x80212fec: 0x7c0018ac, 0x80212ff0: 0x38630020, 0x80212ff8: 0x44000002}
for address, word in opcodes.items():
    section = next(i for i in range(7) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
    assert struct.unpack_from('>I', data, layout[section] + address - layout[18 + section])[0] == word
ghidra_root = root / 'es-vector-source/ghidra'
proof = json.loads((ghidra_root / 'verification.json').read_text())
assert proof['runnerSha256'] == sha(experiment / 'verify_es_vector_ghidra.py')
assert [(row['name'], row['instructions'], row['bytes'], row['discoveredBodyBytes']) for row in proof['records']] == [
    ('ESP_GetTitleId', 38, 152, 152), ('IOS_Ioctlv', 55, 220, 220), ('fn_80242F60', 79, 316, 316)]
for row in proof['records']:
    assert row['assemblySha256'] == sha(ghidra_root / (row['name'] + '.asm'))
    assert row['decompiledSha256'] == sha(ghidra_root / (row['name'] + '.c'))
(output / 'verification.json').write_text(json.dumps({'result': 'READ_ONLY_ES_VECTOR8_TEMP_BUFFER_AND_STALE_PHYSICAL_SOURCE_CONTRACT_PASS',
    'verifierSha256': sha(Path(__file__)), 'observationSha256': sha(output / 'observation.json'),
    'ghidraEvidenceSha256': sha(ghidra_root / 'verification.json'), 'dolSha256': sha(dol), 'mutantsRejected': 2,
    'originalOpcodes': {hex(address): hex(word) for address, word in opcodes.items()},
    'limits': ['Native vector/cache snapshot plus static original wrapper copy-on-success contract; no original IOCTLV execution/title ID response.']}, indent=2) + '\n')
print('PASS read-only vector8/bounce-buffer/stale physical state;12 DOL opcodes/Ghidra172instructions688bytes;2mutants')

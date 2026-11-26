"""Validate prepared actual play-record OPEN before path/packet submission."""
from pathlib import Path
import hashlib
import json
import struct

root = Path('work/private-game/static-recomp')
output = root / 'mass-post-es16-close-open-observer'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = json.loads((output / 'observation.json').read_text())
assert report['builderSha256'] == sha(Path('experiments/wii-static-recomp/observe_post_es16_close_open.py'))
assert report['baseBuildSha256'] == sha(root / 'mass-es-close-after-consumption-boot/build.json')
assert report['records'] == json.loads((root / 'mass-es-close-after-consumption-boot/build.json').read_text())['records']
for path, digest in {**report['sourceHashes'], **report['headerHashes']}.items():
    assert sha(Path(path)) == digest
for row in report['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
assert sha(output / 'es-vector-observer') == report['executableSha256']
assert sha(output / 'observation.log') == report['logSha256']
values = {}
for line in report['observations']:
    if line.startswith('POST_CLOSE_OPEN_'):
        tag, *words = line.split()
        assert tag not in values
        values[tag] = words
path_bytes = b'/title/00000001/00000002/data/play_rec.dat\0'

def check(data):
    assert [int(value,16) for value in data['POST_CLOSE_OPEN_ARGS']] == [
        0x8053ff80,0x935e1060,2,0x8053ffd8,0x935e1020,3,0x80240680,0,0x935e0080]
    assert [int(value,16) for value in data['POST_CLOSE_OPEN_LAYOUT']] == [0xffffffff,0x935e00c0,0,0,21,21,5,5]
    cached = bytes(map(int,data['POST_CLOSE_OPEN_WORK_CACHED']))
    physical = bytes(map(int,data['POST_CLOSE_OPEN_WORK_PHYSICAL']))
    assert len(cached) == len(physical) == 320
    assert cached == path_bytes + bytes(256-len(path_bytes)) + struct.pack('>2I',0x80244e30,0x8049325c) + bytes(56)
    assert physical == path_bytes + bytes(320-len(path_bytes))
    assert bytes(map(int,data['POST_CLOSE_OPEN_PACKET_CACHED'])) == struct.pack(
        '>10I',1,0,0,0x16,1,2,0x8053fd70,0,0x80240680,0x935e1020) + bytes(24)
    assert bytes(map(int,data['POST_CLOSE_OPEN_PACKET_PHYSICAL'])) == struct.pack(
        '>8I',8,0,2,0x16,1,2,0x8053fd70,0) + bytes(32)

check(values)
mutants = 0
for tag, words in values.items():
    for index, value in enumerate(words):
        bad = {key:list(items) for key,items in values.items()}
        hexadecimal = tag in ('POST_CLOSE_OPEN_ARGS','POST_CLOSE_OPEN_LAYOUT')
        changed = int(value,16 if hexadecimal else 10) ^ 1
        bad[tag][index] = format(changed,'x') if hexadecimal else str(changed)
        try:
            check(bad)
        except AssertionError:
            mutants += 1
        else:
            raise AssertionError('Prepared play-record OPEN mutation accepted')
assert mutants == 785
lab = Path('_scratch/tmp/dolphin-es-close-after-consumption-disc-user/Wii/title/00000001/00000002/data/play_rec.dat')
assert lab.stat().st_size == 128
(output / 'comparison.json').write_text(json.dumps({'result':'NATIVE_PREPARED_SYSTEM_MENU_PLAY_RECORD_OPEN_MODE3_CALLBACK_OWNERS_PASS',
    'verifierSha256':sha(Path(__file__)),'observationSha256':sha(output/'observation.json'),
    'mutantsRejected':mutants,'labFileBytes':128,'labFileSha256':sha(lab),
    'limits':['All125 PPC objects unchanged; before OPEN path normalization/submission, not completed service.',
        'Mode3 read/write and exact IOS/ISFS/nand callback ownership; physical callback tail intentionally not coherent yet.',
        'Lab128 file exists, but its content and original callback behavior still require dynamic verification.',
        'No private LAB file introduced as required game asset; future writes must use separate PC-owned experimental data.']},indent=2)+'\n')
print('PASS native play_rec.dat OPEN mode3/callback owners/cached-vs-physical/785 mutations/ALL125 unchanged; LAB128 not yet executed')

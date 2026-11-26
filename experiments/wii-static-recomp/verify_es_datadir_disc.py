"""Verify original GetDataDir output extent, vectors, replies and pending STM."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
parent = experiment / 'verify_es_disc_oracle.py'
prefix = parent.read_text().split('\ntitle = bytes.fromhex', 1)[0]
prefix = prefix.replace('dolphin-es-disc', 'dolphin-es-datadir-disc').replace(
    'prepare_es_disc_oracle.py', 'prepare_es_datadir_disc.py').replace('run_es_disc_dolphin.ps1', 'run_es_datadir_disc_dolphin.ps1')
prefix = prefix.replace("root / 'dolphin-es-title/generation.json'", "root / 'dolphin-es-datadir/generation.json'")
marker = "body = body[:body.index('\\ndef check_title(')]"
assert prefix.count(marker) == 1
prefix = prefix.replace(marker, marker + "\nbody = body.replace('build_es_title_dolphin.py', 'build_es_datadir_dolphin.py')\n"
    "body = body.replace('[0x80249c40] * 11', '[0x80249c40] + [0x80249ba0] * 10')")
namespace = {'__file__': __file__}
exec(compile(prefix, str(parent), 'exec'), namespace)
globals().update(namespace)
assert preparation['parentPreparerSha256'] == sha(experiment / 'prepare_es_disc_oracle.py')
assert generation['datadirParentSha256'] == sha(experiment / 'build_es_title_dolphin.py')
title = bytes.fromhex(preparation['titleId'])
title_check = (experiment / 'verify_es_disc_oracle.py').read_text().split('\ndef check(row, case):', 1)[1].split('\ncases =', 1)[0]
exec(compile('def check_title(row, case):' + title_check, str(experiment / 'verify_es_disc_oracle.py'), 'exec'), globals())
initial_title = check_title(data[5 * 736:6 * 736], generation['records'][5])
path_bytes = ('/title/' + title[:4].hex() + '/' + title[4:].hex() + '/data').encode('ascii')
assert len(path_bytes) == 29
proof_path = root / 'es-datadir-source/ghidra/verification.json'
proof = json.loads(proof_path.read_text())
assert proof['runnerSha256'] == sha(experiment / 'verify_es_datadir_ghidra.py')
assert [(row['name'], row['instructions'], row['bytes'], row['discoveredBodyBytes']) for row in proof['records']] == [
    ('ESP_GetDataDir', 38, 152, 152)]
for row in proof['records']:
    for suffix, key in (('asm', 'assemblySha256'), ('c', 'decompiledSha256')):
        assert sha(proof_path.parent / (row['name'] + '.' + suffix)) == row[key]


def check_dir(row, case):
    index = case['index']
    assert case['kind'] == 'ESP_GetDataDir'
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    state = list(struct.unpack_from('>22I', row, 24))
    count = index + 2
    assert state[2] in (0x10000, 0x10100)
    assert state == [0x38, 0x135e0080, state[2], 1, 0, 0, 0, 0x80492658, 0x80492658, 0x492658,
        0x80492658, 0x20001, 0, 0x935e0060, 0x50, count, count, count & 15, count & 15, 0x8021a890, 0x2032, 0xa032]
    assert struct.unpack_from('>2I', row, 400) == (0, 0xa032)
    physical = struct.pack('>8I', 8, 0, 7, 0x1d, 1, 1, 0x53ffd0, 0) + bytes(32)
    cached = struct.pack('>8I', 8, 0, 7, 0x1d, 1, 1, 0x8053ffd0, 0) + bytes(32)
    assert row[448:512] == physical and row[512:576] == cached
    assert row[576:608] == row[608:640] == path_bytes + bytes([0xa5]) * 3
    assert row[656:664] == row[664:672] == title
    assert struct.unpack_from('>8I', row, 672) == (0x8053ff00, 8, 0x80500000, 30, 0x53ff00, 8, 0x500000, 30)
    assert struct.unpack_from('>I', row, 640)[0] == 3
    assert row[192:256].hex() == pending['physicalPacketHex'] and row[256:320].hex() == pending['cachedPacketHex']
    assert row[416:448] == bytes(32)
    return {'index': index, 'returnValue': 0, 'states': state, 'path': path_bytes.decode('ascii'),
        'outputBytesWritten': 29, 'outputAdvertisedBytes': 30, 'terminatorWritten': False,
        'physicalReplyHex': physical.hex(), 'cachedReplyHex': cached.hex(),
        'callerPhysicalHex': row[576:608].hex(), 'callerCachedHex': row[608:640].hex(),
        'inputCachedHex': row[656:664].hex(), 'inputPhysicalHex': row[664:672].hex(),
        'vectorCachedHex': row[672:688].hex(), 'vectorPhysicalHex': row[688:704].hex()}


cases = [check_dir(data[i * 736:(i + 1) * 736], generation['records'][i]) for i in range(6, 16)]
locations = [24, 28, 80, 84, 108, 192, 288, 400, 404, 416, 448, 452, 460, 464, 472, 512, 536,
    576, 604, 605, 606, 607, 608, 637, 638, 639, 640, 656, 664, 672, 676, 680, 684, 688, 692, 696, 700]
for location in locations:
    changed = bytearray(data[6 * 736:7 * 736])
    changed[location] ^= 1
    try:
        check_dir(changed, generation['records'][6])
    except AssertionError:
        pass
    else:
        raise AssertionError('Wrong path/added NUL/input/vector/reply/pending accepted')
for address, opcode in ((0x80249bb8, 0x38e100f0), (0x80249bbc, 0x39210020),
    (0x80249bf4, 0x39000008), (0x80249bf8, 0x3800001e), (0x80249bfc, 0x3880001d),
    (0x80249c20, 0x4bff9571)):
    section = next(i for i in range(7) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
    assert struct.unpack_from('>I', original, layout[section] + address - layout[18 + section])[0] == opcode
log = Path('_scratch/tmp/dolphin-es-datadir-disc-user/Logs/dolphin.log')
text = log.read_text(errors='replace')
assert 'Title context changed: ' + title.hex() in text
assert text.count('IOCTL_ES_GETTITLEID:') == 1
assert text.count('IOCTL_ES_GETTITLEDIR: ' + path_bytes.decode('ascii')) == 10
(output / 'disc-comparison.json').write_text(json.dumps({'result': 'ORIGINAL_DISC_GETDATADIR10_OUTPUT29_NO_NUL_GUARDS3_PENDING_STM_PASS',
    'verifierSha256': sha(Path(__file__)), 'preparationSha256': sha(output / 'preparation.json'),
    'generationSha256': sha(output / 'generation.json'), 'captureSha256': sha(capture_path),
    'ghidraSha256': sha(proof_path), 'logSha256': sha(log), 'initialTitle': initial_title,
    'cases': cases, 'mutantsRejected': len(locations),
    'references': ['https://github.com/dolphin-emu/dolphin/blob/2609/Source/Core/Core/IOS/ES/ES.cpp'],
    'limits': ['Original Wii SDK instructions under own-disc Dolphin IOS emulation, custom entry/thread/stack fixtures; not physical IOS or full retail boot.',
        'GetTitleId obtains real context title, ten calls use that saved result. GetDataDir advertises30 but writes29 non-NUL bytes; do not replace with strcpy.',
        'No file/savedata writes, credentials, callback completion or native integration proof.']}, indent=2) + '\n')
print('PASS original GetDataDir10 return0/path29/no added NUL/guards3/both64 replies/vector2/cache/heap/STM;37mutants; Ghidra38/152')

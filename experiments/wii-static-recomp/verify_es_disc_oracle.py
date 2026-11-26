"""Check the same original harness in actual user-disc metadata context, without supplied replies."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'dolphin-es-disc'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
preparation = json.loads((output / 'preparation.json').read_text())
assert preparation['preparerSha256'] == sha(experiment / 'prepare_es_disc_oracle.py')
assert preparation['runnerSha256'] == sha(experiment / 'run_es_disc_dolphin.ps1')
assert preparation['gameID'] == 'R5WEA4' and preparation['revision'] == 0
assert preparation['titleId'] == '0001000052355745' and preparation['iosId'] == '0000000100000035'
source = Path('work/private-game/disc/DATA')
for name, digest in preparation['originalSourceHashes'].items():
    assert sha(source / name) == digest
    if name != 'sys/main.dol':
        assert sha(output / 'DATA' / name) == digest
assert not (output / 'DATA/files').is_symlink()
for record in preparation['assetCopies']:
    original, copy = source / 'files' / record['name'], output / 'DATA/files' / record['name']
    assert original.is_file() and copy.is_file() and original.stat().st_size == copy.stat().st_size == record['bytes']
    assert original.stat().st_ino != copy.stat().st_ino

parent = experiment / 'verify_es_title_dolphin.py'
body = parent.read_text()
# Reuse only the existing initial SDK/vector/provenance gate, not its standalone-error assertions.
body = body[:body.index('\ndef check_title(')]
body = body.replace('dolphin-es-title', 'dolphin-es-disc').replace('run_es_title_dolphin.ps1', 'run_es_disc_dolphin.ps1')
# The disc has the exact standalone harness; its generation manifest is reused privately below.
generation = json.loads((root / 'dolphin-es-title/generation.json').read_text())
assert preparation['harnessSha256'] == preparation['standaloneHarnessSha256'] == generation['harnessSha256'] == sha(output / 'DATA/sys/main.dol')
generation['wrapperSha256'] = sha(experiment / 'run_es_disc_dolphin.ps1')
(output / 'generation.json').write_text(json.dumps(generation, indent=2) + '\n')
# The inherited verifier expects a root-level harness name; redirect its read to the staged directory blob.
body = body.replace("output / 'fpr-init.dol'", "output / 'DATA/sys/main.dol'")
# Initial SDK snapshots are compared unchanged. No guessed title value is fed to execution.
namespace = {'__file__': __file__}
exec(compile(body, str(parent), 'exec'), namespace)
globals().update(namespace)
assert 'DATA/sys/main.dol' in capture['arguments'] or 'DATA\\sys\\main.dol' in capture['arguments']
title = bytes.fromhex(preparation['titleId'])

def check(row, case):
    index = case['index']
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    state = list(struct.unpack_from('>22I', row, 24))
    count = index + 2
    assert state[2] in (0x10000, 0x10100)
    assert state == [0x38, 0x135e0080, state[2], 1, 0, 0, 0, 0x80492658, 0x80492658, 0x492658,
        0x80492658, 0x20001, 0, 0x935e0060, 0x50, count, count, count & 15, count & 15, 0x8021a890, 0x2032, 0xa032]
    assert struct.unpack_from('>2I', row, 400) == (0, 0xa032)
    physical = struct.pack('>8I', 8, 0, 7, 0x20, 0, 1, 0x53ffb0, 0) + bytes(32)
    cached = struct.pack('>8I', 8, 0, 7, 0x20, 0, 1, 0x8053ffb0, 0) + bytes(32)
    assert row[448:512] == physical and row[512:576] == cached
    assert row[576:608] == bytes(32) and row[608:640] == title + bytes([0xa5]) * 24
    assert row[656:664] == row[664:672] == title
    assert struct.unpack_from('>4I', row, 672) == (0x8053fee0, 8, 0x53fee0, 8)
    assert struct.unpack_from('>I', row, 640)[0] == 3
    assert row[192:256].hex() == pending['physicalPacketHex'] and row[256:320].hex() == pending['cachedPacketHex']
    assert row[416:448] == bytes(32)
    return {'index': index, 'returnValue': 0, 'titleId': title.hex(), 'states': state,
        'physicalReplyHex': physical.hex(), 'cachedReplyHex': cached.hex(), 'callerCachedHex': row[608:640].hex(),
        'temporaryCachedHex': row[656:664].hex(), 'temporaryPhysicalHex': row[664:672].hex()}

cases = [check(data[i * 736:(i + 1) * 736], generation['records'][i]) for i in range(5, 16)]
locations = [24, 28, 80, 84, 108, 192, 288, 400, 404, 416, 448, 452, 472, 512, 536, 576, 608, 616, 640, 656, 664, 672, 680]
for location in locations:
    changed = bytearray(data[3680:4416])
    changed[location] ^= 1
    try:
        check(changed, generation['records'][5])
    except AssertionError:
        pass
    else:
        raise AssertionError('Wrong disc title/guard/cache/reply/pending accepted')
log = Path('_scratch/tmp/dolphin-es-disc-user/Logs/dolphin.log')
text = log.read_text(errors='replace')
assert 'Title context changed: 0001000052355745' in text
assert text.count('IOCTL_ES_GETTITLEID: 00010000/52355745') == 11
(output / 'disc-comparison.json').write_text(json.dumps({'result': 'ORIGINAL_DISC_CONTEXT_TITLE_QUERY11_SUCCESS_USER_TMD_MATCH_PENDING_STM',
    'verifierSha256': sha(Path(__file__)), 'preparationSha256': sha(output / 'preparation.json'),
    'captureSha256': sha(output / 'fpr-init-true-dolphin.json'), 'logSha256': sha(log), 'cases': cases, 'mutantsRejected': len(locations),
    'limits': ['Extracted own Wii disc metadata and assets, original SDK instructions in a private custom-entry harness; NOT unmodified full-game or physical-Wii execution.',
        'Disc boot introduces an observed unmasked PI cause bit0x100 in later samples; retained in evidence, not cleared or projected onto native timing.',
        'Structural metadata identity only, not cryptographic TMD/ticket/content verification; no credentials published.']}, indent=2) + '\n')
print('PASS original disc-context title queries11 return0/TMD0001000052355745, output8+guards24/cache/heap/STM;23mutants')

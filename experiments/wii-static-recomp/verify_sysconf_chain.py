"""Verify the completed original SC/IOS file lifecycle, not just the empty buffer."""
from pathlib import Path
import hashlib
import json
import struct
import base64

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
gate = experiment / 'verify_stm_async_dolphin.py'
source = gate.read_text()
prefix = source.split('\nfor key, filename in ', 1)[0]
prefix = prefix.replace('dolphin-stm-async', 'dolphin-sysconf-long-disc').replace(
    'build_stm_async_dolphin.py', 'build_sysconf_long_dolphin.py').replace(
    'run_stm_async_dolphin.ps1', 'run_sysconf_long_disc_dolphin.ps1')
prefix = prefix.replace('0x802421f0, 0x80242cf0]', '0x802421f0, 0x80242cf0] + [0x80247450] + [0x802474f0] * 12')
namespace = {'__file__': __file__}
standalone = root / 'dolphin-sysconf-long'
disc = root / 'dolphin-sysconf-long-disc'
fixture = json.loads((standalone / 'generation.json').read_text())
assert fixture['harnessSha256'] == hashlib.sha256((disc / 'DATA/sys/main.dol').read_bytes()).hexdigest()
(disc / 'generation.json').write_bytes((standalone / 'generation.json').read_bytes())
exec(compile(prefix, str(gate), 'exec'), namespace)
globals().update(namespace)
preparation = json.loads((output / 'preparation.json').read_text())
assert preparation['preparerSha256'] == sha(experiment / 'prepare_sysconf_long_disc.py')
assert preparation['runnerSha256'] == sha(experiment / 'run_sysconf_long_disc_dolphin.ps1')
assert preparation['harnessSha256'] == sha(output / 'DATA/sys/main.dol')
assert preparation['gameID'] == 'R5WEA4' and preparation['revision'] == 0
for name, digest in preparation['originalSourceHashes'].items():
    assert sha(Path('work/private-game/disc/DATA') / name) == digest
assert generation['guestSpinIterationsPerRecord'] == 1000000
assert generation['arenaPrecondition']['low'] == '935e1000' and generation['arenaPrecondition']['high'] == '93600000'
assert generation['sysconfChainParentSha256'] == sha(experiment / 'build_stm_async_dolphin.py')
assert generation['longParentSha256'] == sha(experiment / 'build_sysconf_chain_dolphin.py')
arena_path = root / 'mass-sysconf-arena-native/observation.json'
arena = json.loads(arena_path.read_text())
assert generation['arenaPrecondition']['nativeObservationSha256'] == sha(arena_path)
assert arena['builderSha256'] == sha(experiment / 'observe_sysconf_arena_native.py')
assert 'SC_NATIVE_ARENA 935e2540 93600000 935e1000 93600000 935e1000 1 1' in arena['observations']
for path, digest in {**arena['sourceHashes'], **arena['headerHashes']}.items():
    assert sha(Path(path)) == digest
assert arena['records'] == json.loads((root / 'mass-es-close-boot/build.json').read_text())['records']
pair_source = (experiment / 'verify_stm_pair_dolphin.py').read_text()
function = pair_source.split('\ndef check(row, case):', 1)[1].split('\nobservations =', 1)[0]
exec(compile('def check_pair(row, case):' + function, str(experiment / 'verify_stm_pair_dolphin.py'), 'exec'), globals())
initial_opens = [check_pair(data[i * 736:(i + 1) * 736], generation['records'][i]) for i in range(2)]
pending_function = source.split('\ndef check_pending(row, case):', 1)[1].split('\nobservations =', 1)[0]
exec(compile('def check_pending(row, case):' + pending_function, str(experiment / 'verify_stm_async_dolphin.py'), 'exec'), globals())
pending = check_pending(data[2 * 736:3 * 736], generation['records'][2])
user = Path('_scratch/tmp/dolphin-sysconf-long-disc-user')
sysconf = user / 'Wii/shared2/sys/SYSCONF'
product = user / 'Wii/title/00000001/00000002/data/setting.txt'
conf = sysconf.read_bytes()
assert len(conf) == 0x4000 and product.stat().st_size == 0x100
assert base64.b64decode(capture['confPhysical']) == conf
assert conf[:4] == b'SCv0' and conf[-4:] == b'SCed' and struct.unpack_from('>H', conf, 4)[0] > 0


def check_completed(row, index):
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    assert struct.unpack_from('>2I', row, 400) == (0, 0xa032)
    assert struct.unpack_from('>3I', row, 608) == (0, 1, 1)
    assert struct.unpack_from('>I', row, 644)[0] == 0x8052e720
    assert struct.unpack_from('>3I', row, 720) == (0, 0x4000, 0x100)
    assert row[448:480] == row[480:512] == conf[:32]
    assert row[192:256].hex() == pending['physicalPacketHex']
    assert row[256:320].hex() == pending['cachedPacketHex'] and row[416:448] == bytes(32)
    state = list(struct.unpack_from('>22I', row, 24))
    assert state[:2] == [0x38, 0x135e00e0] and state[2] in (0x10000, 0x10100)
    assert state[3:15] == [1, 0, 0, 0, 0x80492658, 0x80492658, 0x492658, 0x80492658, 0x20001, 0, 0x935e0060, 0x50]
    assert state[15:19] == [15, 15, 15, 15]
    return {'index': index, 'SCCheckStatus': 0, 'flags': [0, 1, 1], 'readLengths': [0x4000, 0x100],
        'states': state, 'cachedHeadHex': row[448:480].hex(), 'physicalHeadHex': row[480:512].hex()}


cases = [check_completed(data[i * 736:(i + 1) * 736], i) for i in range(5, 16)]
assert struct.unpack_from('>I', data, 4 * 736 + 400)[0] == 1
assert struct.unpack_from('>3I', data, 4 * 736 + 608) == (3, 1, 1)
locations = [24, 28, 76, 80, 84, 88, 92, 192, 288, 400, 404, 416, 448, 480, 608, 612, 616, 644, 720, 724, 728]
for location in locations:
    changed = bytearray(data[15 * 736:16 * 736])
    changed[location] ^= 1
    try:
        check_completed(changed, 15)
    except AssertionError:
        pass
    else:
        raise AssertionError('False completion/partial read/lost STM/wrong heap accepted')
log = user / 'Logs/dolphin.log'
text = log.read_text(errors='replace')
for path, physical, length in [('/shared2/sys/SYSCONF', '0x004b31a0', 16384),
    ('/title/00000001/00000002/data/setting.txt', '0x00003800', 256)]:
    assert 'Opening ' + path + ' (mode 1, fd 3)' in text
    assert 'Read(' + path + ', ' + physical + ', ' + str(length) + '): Result 0' in text
    assert 'Close(' + path + '): Result 0' in text
proof = root / 'sysconf-source/ghidra/verification.json'
assert json.loads(proof.read_text())['runnerSha256'] == sha(experiment / 'verify_sysconf_ghidra.py')
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_WHOLE_SC_CHAIN_READS_16384_256_CLOSES_STATUS0_PENDING_PASS',
    'verifierSha256': sha(Path(__file__)), 'preparationSha256': sha(output / 'preparation.json'),
    'generationSha256': sha(output / 'generation.json'), 'captureSha256': sha(capture_path),
    'ghidraSha256': sha(proof), 'logSha256': sha(log), 'initialOpens': initial_opens,
    'initialPending': pending, 'cases': cases, 'mutantsRejected': len(locations),
    'laboratoryConsoleFiles': {'sysconfSha256': sha(sysconf), 'settingSha256': sha(product),
        'source': 'Isolated Dolphin user-directory generated console configuration; NOT game-disc assets/physical Wii NAND.'},
    'limits': ['Native-measured arena precondition, prepared boot/thread/heap; original SDK owns all NAND/FS/ES/file requests and callbacks.',
        'Configured DevKit fallback retained. No forced status, descriptor or file response; physical retail boot/console identity still unverified.',
        'Capture words are authoritative; earlier byte/absolute diagnostic fields are not used to infer SC status or arena. Timing not cycle-exact.']}, indent=2) + '\n')
print('PASS original whole SCInit/files16384+256/CLOSE/status0 cases11/parsed frame/heap/pendingSTM;21mutants; laboratory console data only')

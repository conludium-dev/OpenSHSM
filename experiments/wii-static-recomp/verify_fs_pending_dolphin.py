"""Check original whole FS OPEN/reply/free and preservation of pending STM."""
from pathlib import Path
import hashlib
import json
import struct

parent = Path('experiments/wii-static-recomp/verify_stm_async_dolphin.py')
source = parent.read_text()
prefix = source.split('\nfor key, filename in ', 1)[0]
prefix = prefix.replace('dolphin-stm-async', 'dolphin-fs-pending')
prefix = prefix.replace('build_stm_async_dolphin.py', 'build_fs_pending_dolphin.py')
prefix = prefix.replace('run_stm_async_dolphin.ps1', 'run_fs_pending_dolphin.ps1')
prefix = prefix.replace('0x802421f0, 0x80242cf0]', '0x802421f0, 0x80242cf0] + [0x80242550] * 13')
exec(compile(prefix, str(parent), 'exec'), globals())
for key, filename in (('sleepParentSha256', 'build_stm_irq_dolphin.py'), ('sendParentSha256', 'build_stm_sleep_dolphin.py'),
    ('pairParentSha256', 'build_stm_send_dolphin.py'), ('asyncParentSha256', 'build_stm_pair_dolphin.py'),
    ('fsParentSha256', 'build_stm_async_dolphin.py')):
    assert generation[key] == sha(experiment / filename)
pair = experiment / 'verify_stm_pair_dolphin.py'
function = pair.read_text().split('\ndef check(row, case):', 1)[1].split('\nobservations =', 1)[0]
exec(compile('def check_pair(row, case):' + function, str(pair), 'exec'), globals())
initial = [check_pair(data[i * 736:(i + 1) * 736], generation['records'][i]) for i in range(2)]
function = source.split('\ndef check_pending(row, case):', 1)[1].split('\nobservations =', 1)[0]
exec(compile('def check_pending(row, case):' + function, str(parent), 'exec'), globals())
pending = check_pending(data[1472:2208], generation['records'][2])

def check_fs(row, case):
    index = case['index']
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    count = index + 2
    state = list(struct.unpack_from('>22I', row, 24))
    assert state == [0x38, 0x135e0080, 0x10000, 1, 0, 0, 0, 0x80492658, 0x80492658, 0x492658,
        0x80492658, 0x20001, 0, 0x935e0060, 0x50, count, count, count & 15, count & 15, 0x8021a890, 0x2032, 0xa032]
    assert row[192:256].hex() == pending['physicalPacketHex'] and row[256:320].hex() == pending['cachedPacketHex']
    result = index - 1 if index < 10 else -6
    assert struct.unpack_from('>2I', row, 400) == (result & 0xffffffff, 0xa032)
    reply = struct.pack('>5I', 8, result & 0xffffffff, 1, 0x135e1000, 0) + bytes(44)
    assert row[448:512] == row[512:576] == reply
    assert row[576:640] == (case['fsPath'].encode() + b'\0').ljust(64, b'\0')
    assert row[416:448] == bytes(32)
    return {'index': index, 'returnValue': result, 'states': state, 'replyPhysicalHex': row[448:512].hex(),
        'replyCachedHex': row[512:576].hex(), 'pathHex': row[576:640].hex(), 'pendingPhysicalHex': row[192:256].hex(),
        'pendingCachedHex': row[256:320].hex()}

observations = [check_fs(data[i * 736:(i + 1) * 736], generation['records'][i]) for i in range(3, 16)]
locations = [24, 28, 36, 68, 76, 80, 84, 108, 192, 204, 288, 400, 404, 416, 448, 452, 460, 512, 576]
for location in locations:
    mutant = bytearray(data[2208:2944])
    mutant[location] ^= 1
    try:
        check_fs(mutant, generation['records'][3])
    except AssertionError:
        pass
    else:
        raise AssertionError('FS result/reply/path/pending/heap mutation accepted')
for address, opcode in ((0x802405d8, 0x48001f79), (0x80242550, 0x9421ffe0)):
    section = next(i for i in range(7) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
    assert struct.unpack_from('>I', original, layout[section] + address - layout[18 + section])[0] == opcode
proof_path = root / 'fs-open-source/ghidra/verification.json'
proof = json.loads(proof_path.read_text())
assert proof['runnerSha256'] == sha(experiment / 'verify_fs_open_ghidra.py')
assert [(row['name'], row['instructions'], row['bytes'], row['discoveredBodyBytes']) for row in proof['records']] == [
    ('ISFS_OpenLib', 74, 296, 296), ('IOS_Open', 73, 292, 288)]
for row in proof['records']:
    assert row['assemblySha256'] == sha(proof_path.parent / (row['name'] + '.asm'))
    assert row['decompiledSha256'] == sha(proof_path.parent / (row['name'] + '.c'))
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_FS_OPEN7_FD2_TO8_MISSING6_PENDING_STM_AND_HEAP_PRESERVED',
    'verifierSha256': sha(Path(__file__)), 'baseVerifierSha256': sha(parent), 'generationSha256': sha(output / 'generation.json'),
    'captureSha256': sha(capture_path), 'initialOpens': initial, 'initialPending': pending,
    'observations': observations, 'mutantsRejected': len(locations), 'ghidraEvidenceSha256': sha(proof_path),
    'limits': generation['limits']}, indent=2) + '\n')
print('PASS original whole IOS_Open: FS7 FD2..8, missing6=-6; both64 replies, heap reuse, STM pending retained;19mutants')

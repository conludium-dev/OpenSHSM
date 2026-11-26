"""Check whole SDK close, no-send repeated close, invalid raw close and FD reuse."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
gate = experiment / 'verify_es_datadir_disc.py'
prefix = gate.read_text().split('\ncases =', 1)[0]
prefix = prefix.replace('dolphin-es-datadir', 'dolphin-es-close').replace(
    'prepare_es_datadir_disc.py', 'prepare_es_close_disc.py').replace(
    'run_es_datadir_disc_dolphin.ps1', 'run_es_close_disc_dolphin.ps1').replace(
    'build_es_datadir_dolphin.py', 'build_es_close_dolphin.py')
prefix = prefix.replace('[0x80249c40] + [0x80249ba0] * 10',
    '[0x80249c40, 0x80249ba0, 0x802497f0, 0x802497f0, 0x80242740, 0x80249790, 0x802497f0, 0x80242740, 0x802497f0, 0x80249790, 0x802497f0]')
namespace = {'__file__': __file__}
exec(compile(prefix, str(gate), 'exec'), namespace)
globals().update(namespace)
assert preparation['closeParentPreparerSha256'] == sha(experiment / 'prepare_es_datadir_disc.py')
assert generation['closeParentSha256'] == sha(experiment / 'build_es_datadir_dolphin.py')
initial_directory = check_dir(data[6 * 736:7 * 736], generation['records'][6])
proof_path = root / 'es-close-source/ghidra/verification.json'
proof = json.loads(proof_path.read_text())
assert proof['runnerSha256'] == sha(experiment / 'verify_es_close_ghidra.py')
assert [(row['name'], row['instructions'], row['bytes'], row['discoveredBodyBytes']) for row in proof['records']] == [
    ('ESP_CloseLib', 18, 72, 72), ('fn_80242740', 42, 168, 168)]
for row in proof['records']:
    for suffix, key in (('asm', 'assemblySha256'), ('c', 'decompiledSha256')):
        assert sha(proof_path.parent / (row['name'] + '.' + suffix)) == row[key]
counts = {7: 9, 8: 9, 9: 10, 10: 11, 11: 12, 12: 13, 13: 13, 14: 14, 15: 15}


def check_close(row, case):
    index = case['index']
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    state = list(struct.unpack_from('>22I', row, 24))
    count = counts[index]
    assert state[2] in (0x10000, 0x10100)
    assert state == [0x38, 0x135e0080, state[2], 1, 0, 0, 0, 0x80492658, 0x80492658, 0x492658,
        0x80492658, 0x20001, 0, 0x935e0060, 0x50, count, count, count & 15, count & 15, 0x8021a890, 0x2032, 0xa032], (index, state)
    expected_return = 0xfffffffc if index in (9, 12) else 0
    assert struct.unpack_from('>2I', row, 400) == (expected_return, 0xa032)
    reopened = index in (10, 14)
    assert struct.unpack_from('>I', row, 640)[0] == (3 if reopened else 0xffffffff)
    result = 3 if reopened else 0xfffffffc if index in (9, 12, 13) else 0
    header = (8, result, 1 if reopened else 2,
        0x53ffd0 if index < 10 else 0x528cf0, 1 if index < 10 else 0, 1, 0x8053ffd0, 0)
    # The stale directory vector remains virtual even in the physical CLOSE packet.
    if index < 10:
        header = header[:3] + (0x1d,) + header[4:]
    reply = struct.pack('>8I', *header) + bytes(32)
    assert row[448:512] == row[512:576] == reply
    assert row[576:608] == row[608:640] == path_bytes + bytes([0xa5]) * 3
    assert row[192:256].hex() == pending['physicalPacketHex'] and row[256:320].hex() == pending['cachedPacketHex']
    assert row[416:448] == bytes(32)
    return {'index': index, 'kind': case['kind'], 'returnValue': -4 if expected_return else 0,
        'sdkFd': 3 if reopened else -1, 'ipcQueueCount': count, 'submitted': index not in (8, 13),
        'states': state, 'physicalReplyHex': reply.hex(), 'cachedReplyHex': reply.hex()}


cases = [check_close(data[i * 736:(i + 1) * 736], generation['records'][i]) for i in range(7, 16)]
locations = [24, 28, 80, 84, 88, 92, 108, 192, 288, 400, 404, 416, 448, 452, 456, 460, 464, 472, 512, 576, 605, 608, 637, 640]
mutants = 0
for index in (7, 8, 9, 10, 13):
    for location in locations:
        changed = bytearray(data[index * 736:(index + 1) * 736])
        changed[location] ^= 1
        try:
            check_close(changed, generation['records'][index])
        except AssertionError:
            mutants += 1
        else:
            raise AssertionError('Wrong CLOSE result/FD/no-send/stale reply/queue/pending accepted')
for address, opcode in ((0x8024980c, 0x4bff8f35), (0x8024981c, 0x3800ffff),
    (0x80249820, 0x900da5c8), (0x80242798, 0x38000002), (0x802427b0, 0x93c30008), (0x802427c4, 0x4bfffa2d)):
    section = next(i for i in range(7) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
    assert struct.unpack_from('>I', original, layout[section] + address - layout[18 + section])[0] == opcode
log = Path('_scratch/tmp/dolphin-es-close-disc-user/Logs/dolphin.log')
text = log.read_text(errors='replace')
assert text.count('IOCTL_ES_GETTITLEID:') == 1 and text.count('IOCTL_ES_GETTITLEDIR:') == 1
(output / 'disc-comparison.json').write_text(json.dumps({'result': 'ORIGINAL_ES_CLOSE3_REOPEN2_RAW_INVALID2_NOSEND2_PENDING_PASS',
    'verifierSha256': sha(Path(__file__)), 'preparationSha256': sha(output / 'preparation.json'),
    'generationSha256': sha(output / 'generation.json'), 'captureSha256': sha(capture_path),
    'ghidraSha256': sha(proof_path), 'logSha256': sha(log), 'initialTitle': initial_title,
    'initialDirectory': initial_directory, 'cases': cases, 'mutantsRejected': mutants,
    'limits': ['Whole original SDK/raw close under own-disc Dolphin IOS, custom-entry/thread/heap fixture; not physical or unmodified retail execution.',
        'Already-closed SDK calls do not submit IPC; after invalid raw close the old physical -4 reply persists while SDK call returns0.',
        'Three closes invalidate SDK FD, two reopens reuseFD3. No savedata file writes, callback completion or native integration proof.']}, indent=2) + '\n')
print('PASS original ES CLOSE3/FD-1/reopen2-FD3/raw-invalid2=-4/no-send2/stale64reply/heap/STM;120mutants;Ghidra60/240')

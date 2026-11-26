"""Verify ACK retains the prior ARM pointer, not the new FS request pointer."""
from pathlib import Path
import hashlib
import json
import struct

parent = Path('experiments/wii-static-recomp/verify_stm_pair_ack_dolphin.py')
prefix = parent.read_text().split('\nassert generation[', 1)[0]
prefix = prefix.replace('dolphin-stm-pair-ack', 'dolphin-fs-ack').replace('build_stm_pair_ack_dolphin.py', 'build_fs_ack_dolphin.py')
prefix = prefix.replace('run_stm_pair_ack_dolphin.ps1', 'run_fs_ack_dolphin.ps1').replace('[0x80241c30] * 66', '[0x80241c30] * 65')
exec(compile(prefix, str(parent), 'exec'), globals())
assert generation['ackPairParentSha256'] == sha(experiment / 'build_stm_open_dolphin.py')
assert generation['fsAckParentSha256'] == sha(experiment / 'build_stm_pair_ack_dolphin.py')

def check(row, case):
    i, physical = case['index'], case['physical']
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I', row, 16) == (0xc001cafe, i)
    prior = 0 if i == 0 else 0x135e0020 if i <= 3 else physical - 64
    state = list(struct.unpack_from('>18I', row, 24))
    expected = [0x38 if not i else 0x30, 0, 0x31, 0x32, prior, 0x10000,
        0 if i == 2 else 0x34, 0 if i == 2 else physical, 0 if i == 2 else 0x10000,
        0x30, 0, 0, 0x14000, 0x2032, physical, 0, physical, case['messageReturn']]
    assert state == expected, (i, state, expected)
    assert physical == (0x135e0020 if i < 3 else 0x135e0080 + (i - 3) * 64)
    path = (0x4398f0 if i == 0 else 0x439904) if i < 3 else 0x135e1000
    if i != 2:
        result = i if i < 2 else i - 1
        assert row[192:256] == struct.pack('>5I', 8, result, 1, path, 0) + bytes(44)
    if i >= 2:
        pending = struct.pack('>8I', 6, 0, 1, 0x1000, 0x493060, 32, 0x493080, 32) + bytes(32)
        assert row[256:320] == pending
        assert row[320:384] == data[320:384] == struct.pack('>5I', 8, 0, 1, 0x4398f0, 0) + bytes(44)
    return {'index': i, 'physical': physical, 'priorArm': prior, 'states': state,
        'replyHex': row[192:256].hex() if i != 2 else None, 'pendingHex': row[256:320].hex() if i >= 2 else None}

observations = [check(data[i * 736:(i + 1) * 736], case) for i, case in enumerate(generation['records'])]
for offset in (36, 40, 48, 52, 64, 68, 196, 204, 256, 268, 320):
    mutant = bytearray(data[2208:2944])
    mutant[offset] ^= 1
    try:
        check(mutant, generation['records'][3])
    except AssertionError:
        pass
    else:
        raise AssertionError('Changed-pointer ACK/reply/pending mutation accepted')
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_FS_ACK13_CHANGED_POINTER_RETAINS_PRIOR_ARM_PENDING_STM',
    'verifierSha256': sha(Path(__file__)), 'generationSha256': sha(output / 'generation.json'), 'captureSha256': sha(capture_path),
    'observations': observations, 'mutantsRejected': 11, 'limits': generation['limits']}, indent=2) + '\n')
print('PASS original FS ACK13 changed pointers retain previous ARM pointer, pending STM intact;11mutants')

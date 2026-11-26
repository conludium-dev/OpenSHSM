"""Verify original whole sender and real heap allocation/free with CPU-delivered reply."""
from pathlib import Path
import hashlib
import json
import struct

parent = Path('experiments/wii-static-recomp/verify_stm_sleep_dolphin.py')
prefix = parent.read_text().rsplit('def check(row, case):', 1)[0]
prefix = prefix.replace('dolphin-stm-sleep', 'dolphin-stm-send')
prefix = prefix.replace('build_stm_sleep_dolphin.py', 'build_stm_send_dolphin.py')
prefix = prefix.replace('run_stm_sleep_dolphin.ps1', 'run_stm_send_dolphin.ps1')
prefix = prefix.replace('([0x80241c30] * 4 + [0x8021b4e0])',
    '([0x80241c30] * 2 + [0x80243570, 0x802438a0, 0x802421f0])')
exec(compile(prefix, str(parent), 'exec'), globals())
assert generation['sendParentSha256'] == sha(experiment / 'build_stm_sleep_dolphin.py')

def check(row, case):
    index, physical = case['index'], case['physical']
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    state = list(struct.unpack_from('>40I', row, 24))
    expected = [0x30, 0, 0x38, physical, 0x10000, 1, 0, 0, 0, 0x80492658, 0, 0, 0, 0x2032,
        physical, 0, 0, 0, 0x8021a8e0, 27, 0x8021a890, 0x2032,
        0x8053ffc0, 0x805335e0, 0x8052e720, 0, 0x00020001, 16, 0, 0, 0,
        0x8021a8e0, 0x8032, 0x80492658, 0x492658, 0x80492658,
        0x80540000, 0x805335e0, 0x8052e720, 0xc0680000 + index * 736]
    assert state == expected, (index, state, expected)
    result = index if index < 8 else -6
    heap = list(struct.unpack_from('>13I', row, 320))
    arena = (physical | 0x80000000) - 32
    assert heap == [result & 0xffffffff, physical | 0x80000000, 0, arena, 0, 4096,
        arena, 0xbabe0000, 4080, 2, 2, 2, 2], (index, heap)
    packet = struct.pack('>5I', 8, result & 0xffffffff, 1, case['pathAddress'], 0) + bytes(44)
    assert row[192:256] == row[256:320] == packet
    return {'index': index, 'states': state, 'heap': heap, 'replyResult': result,
        'physicalPacketHex': packet.hex(), 'cachedPacketHex': packet.hex()}

observations = [check(data[i * 736:(i + 1) * 736], case) for i, case in enumerate(generation['records'])]
for location in (60, 76, 104, 112, 128, 156, 168, 196, 300, 320, 324, 328, 336, 360, 368):
    mutant = bytearray(data[:736])
    mutant[location] ^= 1
    try:
        check(mutant, generation['records'][0])
    except AssertionError:
        pass
    else:
        raise AssertionError('Sender/context/heap/payload mutation accepted')
proofs = {}
for directory in ('ios-transport', 'ios-open-allocator', 'ios-open-free', 'ios-sleep', 'ios-select-thread',
    'ios-save-context', 'ios-load-context', 'ios-set-context', 'ios-ipc-interrupt', 'ios-wakeup', 'dolphin-flush-syscall'):
    path = root / directory / 'ghidra/verification.json'
    proof = json.loads(path.read_text())
    for record in proof['records']:
        assert record['assemblySha256'] == sha(path.parent / (record['name'] + '.asm'))
        assert record['decompiledSha256'] == sha(path.parent / (record['name'] + '.c'))
    proofs[directory] = sha(path)
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_SEND16_ALLOCATE_FLUSH_SUBMIT_SLEEP_IRQ_RETURN_FREE_PASS',
    'verifierSha256': sha(Path(__file__)), 'parentVerifierSha256': sha(parent), 'generationSha256': sha(output / 'generation.json'),
    'captureSha256': sha(capture_path), 'observations': observations, 'mutantsRejected': 15,
    'ghidraEvidence': proofs, 'limits': generation['limits']}, indent=2) + '\n')
print('PASS16 original whole sender/heap allocation-free/flush/sleep/IRQ/result;15mutants/Ghidra hashes')

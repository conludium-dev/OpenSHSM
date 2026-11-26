"""Validate original uninterrupted immediate/eventhook OPENs and retained reply registers."""
from pathlib import Path
import hashlib
import json
import struct

parent = Path('experiments/wii-static-recomp/verify_stm_send_dolphin.py')
prefix = parent.read_text().split('\ndef check(row, case):', 1)[0]
prefix = prefix.replace('dolphin-stm-send', 'dolphin-stm-pair').replace('build_stm_send_dolphin.py', 'build_stm_pair_dolphin.py').replace('run_stm_send_dolphin.ps1', 'run_stm_pair_dolphin.ps1')
prefix = prefix.replace("'([0x80241c30] * 2 + [0x80243570, 0x802438a0, 0x802421f0])'", "'([0x80241c30] * 2 + [0x80243570]) + [target for _ in range(16) for target in (0x802438a0, 0x802421f0)]'")
prefix = prefix.replace("exec(compile(prefix, str(parent), 'exec'), globals())", "prefix = prefix.replace('assert targets == [target for _ in range(16) for target in ([0x80241c30] * 2 + [0x80243570]) + [target for _ in range(16) for target in (0x802438a0, 0x802421f0)]]', 'assert targets == [0x80241c30, 0x80241c30, 0x80243570] + [target for _ in range(16) for target in (0x802438a0, 0x802421f0)]')\nexec(compile(prefix, str(parent), 'exec'), globals())", 1)
exec(compile(prefix, str(parent), 'exec'), globals())
assert generation['pairParentSha256'] == sha(experiment / 'build_stm_send_dolphin.py')

def check(row, case):
    index, physical = case['index'], case['physical']
    assert physical == 0x135e0020
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    state = list(struct.unpack_from('>40I', row, 24))
    expected = [0x38 if index else 0x30, 0, 0x38, physical, 0x10000, 1, 0, 0, 0, 0x80492658, 0, 0, 0, 0x2032,
        physical, 0, 0, 0, 0x8021a8e0, 27, 0x8021a890, 0x2032, 0x8053ffc0, 0x805335e0, 0x8052e720, 0,
        0x20001, 16, 0, 0, 0, 0x8021a8e0, 0x8032, 0x80492658, 0x492658, 0x80492658,
        0x80540000, 0x805335e0, 0x8052e720, 0xc0680000 + index * 736]
    assert state == expected, (index, state)
    heap = list(struct.unpack_from('>13I', row, 320))
    assert heap == [index, 0x935e0020, 0, 0x935e0000, 0, 4096, 0x935e0000, 0xbabe0000, 4080,
        index + 2, index + 2, (index + 2) & 15, (index + 2) & 15], (index, heap)
    before = list(struct.unpack_from('>3I', row, 384))
    assert before == [physical if index else 0, 0, 0], (index, before)
    path = 0x4398f0 if not index % 2 else 0x439904
    assert case['pathAddress'] == path
    packet = struct.pack('>5I', 8, index, 1, path, 0) + bytes(44)
    assert row[192:256] == row[256:320] == packet
    return {'index': index, 'states': state, 'heap': heap, 'beforeRegisters': before, 'replyResult': index,
        'physicalPacketHex': packet.hex(), 'cachedPacketHex': packet.hex()}

observations = [check(data[i * 736:(i + 1) * 736], case) for i, case in enumerate(generation['records'])]
for location in (24, 76, 104, 112, 128, 156, 196, 300, 320, 324, 336, 360, 368, 384, 388, 392):
    mutant = bytearray(data[736:1472])
    mutant[location] ^= 1
    try:
        check(mutant, generation['records'][1])
    except AssertionError:
        pass
    else:
        raise AssertionError('Consecutive/reuse/register/payload mutant accepted')
prior = json.loads((root / 'dolphin-stm-send/comparison.json').read_text())
for directory, digest in prior['ghidraEvidence'].items():
    assert sha(root / directory / 'ghidra/verification.json') == digest
    proof = json.loads((root / directory / 'ghidra/verification.json').read_text())
    for record in proof['records']:
        assert sha(root / directory / 'ghidra' / (record['name'] + '.asm')) == record['assemblySha256']
        assert sha(root / directory / 'ghidra' / (record['name'] + '.c')) == record['decompiledSha256']
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_CONSECUTIVE_STM16_IMMEDIATE_EVENTHOOK_HEAP_QUEUE_ARM_REUSE_PASS',
    'verifierSha256': sha(Path(__file__)), 'generationSha256': sha(output / 'generation.json'), 'captureSha256': sha(capture_path),
    'observations': observations, 'mutantsRejected': 16, 'ghidraEvidence': prior['ghidraEvidence'], 'limits': generation['limits']}, indent=2) + '\n')
print('PASS16 consecutive original immediate/eventhook OPEN/heap/queue wrap/retainedARM;16mutants')

"""Verify original real sleep, idle IRQ, selected current context and synchronous return."""
from pathlib import Path
import hashlib
import json
import struct

parent = Path('experiments/wii-static-recomp/verify_stm_irq_dolphin.py')
prefix = parent.read_text().split('def check(row, case):', 1)[0]
prefix = prefix.replace("cached = '--cached' in sys.argv", 'cached = True')
for name in ('dolphin-stm-irq-cache', 'dolphin-stm-irq'):
    prefix = prefix.replace("'" + name + "'", "'dolphin-stm-sleep'")
for name in ('build_stm_irq_cache_dolphin.py', 'build_stm_irq_dolphin.py'):
    prefix = prefix.replace("'" + name + "'", "'build_stm_sleep_dolphin.py'")
for name in ('run_stm_irq_cache_dolphin.ps1', 'run_stm_irq_dolphin.ps1'):
    prefix = prefix.replace("'" + name + "'", "'run_stm_sleep_dolphin.ps1'")
prefix = prefix.replace("generation['cacheParentSha256'] == sha(experiment / 'build_stm_sleep_dolphin.py')",
    "generation['sleepParentSha256'] == sha(experiment / 'build_stm_irq_dolphin.py')")
prefix = prefix.replace('assert targets == [0x80241c30] * 64',
    'assert targets == [target for _ in range(16) for target in ([0x80241c30] * 4 + [0x8021b4e0])]')
exec(compile(prefix, str(parent), 'exec'), globals())
def check(row, case):
    index, physical = case['index'], case['physical']
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    state = list(struct.unpack_from('>40I', row, 24))
    expected = [0x38, 0, 0x38, physical, 0x10000, 1, 0, 0, 0, 0x80492658, 0, 0, 0, 0x2032,
        physical, 0, physical, case['messageReturn'], 0x8021a8e0, 27, 0x8021a890, 0x2032,
        0x8053ffe0, 0x805335e0, 0x8052e720, 0, 0x00020001, 16, 0, 0, 0,
        0x8021a8e0, 0x8032, 0x80492658, 0x492658, 0x80492658,
        0x80540000, 0x805335e0, 0x8052e720, 0xc0680000 + index * 736]
    assert state == expected, (index, state, expected)
    result = index if index < 8 else -6
    packet = struct.pack('>5I', 8, result & 0xffffffff, 1, case['pathAddress'], 0) + bytes(44)
    assert row[192:256] == row[256:320] == packet
    return {'index': index, 'states': state, 'replyResult': result, 'physicalPacketHex': packet.hex(), 'cachedPacketHex': packet.hex()}
observations = [check(data[i * 736:(i + 1) * 736], case) for i, case in enumerate(generation['records'])]
for location in (60, 76, 96, 104, 128, 152, 156, 168, 196, 300):
    mutant = bytearray(data[:736])
    mutant[location] ^= 1
    try:
        check(mutant, generation['records'][0])
    except AssertionError:
        pass
    else:
        raise AssertionError('Sleep/idle-context/ABI/payload mutation accepted')
proofs = {}
for directory in ('ios-sleep', 'ios-select-thread', 'ios-save-context', 'ios-load-context', 'ios-set-context', 'ios-ipc-interrupt', 'ios-wakeup'):
    path = root / directory / 'ghidra/verification.json'
    proof = json.loads(path.read_text())
    for record in proof['records']:
        assert record['assemblySha256'] == sha(path.parent / (record['name'] + '.asm'))
        assert record['decompiledSha256'] == sha(path.parent / (record['name'] + '.c'))
    proofs[directory] = sha(path)
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_OSSLEEP16_IDLE_IRQ_WAKES_CURRENT_THREAD_SYNCHRONOUS_RETURN_PASS',
    'verifierSha256': sha(Path(__file__)), 'parentVerifierSha256': sha(parent), 'generationSha256': sha(output / 'generation.json'),
    'captureSha256': sha(capture_path), 'observations': observations, 'mutantsRejected': 10, 'ghidraEvidence': proofs,
    'limits': generation['limits']}, indent=2) + '\n')
print('PASS16 realoriginal OSSleep→idleIRQ27→Wakeup→Select/OSLoadContext/rfi→caller;10mutants')

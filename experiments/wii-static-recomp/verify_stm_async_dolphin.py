"""Verify original async return/CPU ACK and finite pending request/cache/heap observations."""
from pathlib import Path
import hashlib
import json
import struct

parent = Path('experiments/wii-static-recomp/verify_stm_irq_dolphin.py')
prefix = parent.read_text().split('\ndef check(row, case):', 1)[0]
prefix = prefix.replace("cached = '--cached' in sys.argv", 'cached = False')
prefix = prefix.replace("name = 'dolphin-stm-irq-cache' if cached else 'dolphin-stm-irq'", "name = 'dolphin-stm-async'")
prefix = prefix.replace("builder = 'build_stm_irq_cache_dolphin.py' if cached else 'build_stm_irq_dolphin.py'", "builder = 'build_stm_async_dolphin.py'")
prefix = prefix.replace("wrapper = 'run_stm_irq_cache_dolphin.ps1' if cached else 'run_stm_irq_dolphin.ps1'", "wrapper = 'run_stm_async_dolphin.ps1'")
prefix = prefix.replace('assert targets == [0x80241c30] * 64',
    'assert targets == [0x80241c30, 0x80241c30, 0x80243570, 0x802438a0, 0x802421f0, 0x802438a0, 0x802421f0, 0x80242cf0]')
exec(compile(prefix, str(parent), 'exec'), globals())
for key, filename in (('sleepParentSha256', 'build_stm_irq_dolphin.py'), ('sendParentSha256', 'build_stm_sleep_dolphin.py'),
    ('pairParentSha256', 'build_stm_send_dolphin.py'), ('asyncParentSha256', 'build_stm_pair_dolphin.py')):
    assert generation[key] == sha(experiment / filename)
pair_verifier = experiment / 'verify_stm_pair_dolphin.py'
function = pair_verifier.read_text().split('\ndef check(row, case):', 1)[1].split('\nobservations =', 1)[0]
exec(compile('def check_pair(row, case):' + function, str(pair_verifier), 'exec'), globals())
initial = [check_pair(data[i * 736:(i + 1) * 736], generation['records'][i]) for i in range(2)]

def check_pending(row, case):
    index = case['index']
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    state = list(struct.unpack_from('>22I', row, 24))
    assert state == [0x30, 0x135e0020, 0x10000, 1, 0, 0, 0, 0x80492658, 0x80492658, 0x492658,
        0x80492658, 0x20001, 0, 0x935e0060, 0x50, 4, 4, 4, 4, case['asyncCall'] + 40, 0xa032, 0xa032], (index, state)
    header = struct.pack('>8I', 6, 1, 1, 0x1000, 0x493060, 32, 0x493080, 32)
    assert row[192:256] == header + bytes(32)
    assert row[256:320] == header + struct.pack('>8I', 0x8021cc70, 0, 0, 0, 0, 0, 0, 0)
    assert struct.unpack_from('>2I', row, 400) == ((0, 0x2032) if index == 2 else (0, 0))
    assert row[416:448] == bytes(32)
    return {'index': index, 'states': state, 'physicalPacketHex': row[192:256].hex(),
        'cachedPacketHex': row[256:320].hex(), 'outputHex': row[416:448].hex(), 'spinInstructions': case['spinInstructions']}

observations = [check_pending(data[i * 736:(i + 1) * 736], generation['records'][i]) for i in range(2, 16)]
for location in (24, 28, 36, 68, 76, 80, 84, 108, 192, 204, 288, 292, 296, 400, 404, 416):
    mutant = bytearray(data[1472:2208])
    mutant[location] ^= 1
    try:
        check_pending(mutant, generation['records'][2])
    except AssertionError:
        pass
    else:
        raise AssertionError('Async return/ACK/pending/cache/output mutant accepted')
proof_path = root / 'stm-async-source/ghidra/verification.json'
proof = json.loads(proof_path.read_text())
for record in proof['records']:
    assert sha(proof_path.parent / (record['name'] + '.asm')) == record['assemblySha256']
    assert sha(proof_path.parent / (record['name'] + '.c')) == record['decompiledSha256']
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_ASYNC_RETURN0_ACK30_PENDING_CMD6_CACHED_CALLBACK_FINITE_WINDOW_PASS',
    'verifierSha256': sha(Path(__file__)), 'baseVerifierSha256': sha(parent), 'generationSha256': sha(output / 'generation.json'),
    'captureSha256': sha(capture_path), 'initialOpens': initial, 'observations': observations, 'mutantsRejected': 16,
    'ghidraEvidenceSha256': sha(proof_path), 'limits': generation['limits']}, indent=2) + '\n')
print('PASS original IOS_IoctlAsync returns0/EEoff, CPU ACK,14 bounded pending snapshots/no reply/cached callback;16mutants')

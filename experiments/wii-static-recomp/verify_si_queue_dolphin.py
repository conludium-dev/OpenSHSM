"""Verify queued SI completion, CPU vector return and preserved populated-context profile."""
from pathlib import Path
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'verify_si_irq_dolphin.py'
body = parent.read_text().split('values = []')[0]
body = body.replace('dolphin-si-irq', 'dolphin-si-queue').replace('build_si_irq_dolphin.py', 'build_si_queue_dolphin.py')
body = body.replace('run_si_irq_dolphin.ps1', 'run_si_queue_dolphin.ps1')
exec(compile(body, str(parent), 'exec'), globals())
assert generation['queueParentSha256'] == sha(experiment / 'build_si_vector_dolphin.py')
assert generation['contextEvidenceSha256'] == sha(Path('work/private-game/static-recomp/mass-interrupt-context-observer/audit.json'))
vector = list(struct.unpack_from('>38I', original, offset(0x80211ba0, original_header)))
assert vector[26] == 0x38600000
vector[26] = 0x38600004
assert generation['vectorWords'] == vector
assert list(struct.unpack('>38I', base64.b64decode(capture['vectorCode']))) == vector
main_start = offset(0x80600000, header)
main_end = offset(min(patch['trampoline'] for patch in generation['patches']), header)
words = struct.unpack('>' + 'I' * ((main_end - main_start) // 4), image[main_start:main_end])
calls = []
for index, word in enumerate(words):
    if word >> 26 == 18 and word & 3 == 1:
        delta = word & 0x03fffffc
        if delta & 0x02000000:
            delta -= 0x04000000
        calls.append(0x80600000 + index * 4 + delta)
assert calls == [0x8020fd00] * 16
def check(row, case, entry):
    index = case['index']
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    completed = list(struct.unpack_from('>11I', row, 448))
    assert completed == [8, 8, 8, 8, 0xffffffff, 0xffffffff, 0xffffffff, 0xffffffff, 0xffffffff, 0, 0x80492658], completed
    context = list(struct.unpack_from('>12I', row, 112))
    assert context[0] == context[2] == 0xa032
    assert entry['wait'] <= context[1] < entry['waitEnd']
    assert context[3:10] == [0x80540000, 0x805335e0, 0x8052e720, 0xc0680000 + index * 736, 0, 0, 0], context
    assert context[10] == context[1] and context[11] == 20
    scalar = list(struct.unpack_from('>22I', row, 24))
    assert scalar[14] == 0x10008 and scalar[18] == 0x10000
    assert scalar[20] == (case['channel'] + 3) % 4 and scalar[21] == 8
    return {'index': index, 'channel': case['channel'], 'scalar': scalar, 'context': context, 'completed': completed}
states = [check(data[i * 736:(i + 1) * 736], case, generation['vectorRecords'][i]) for i, case in enumerate(generation['records'])]
for location in (448, 464, 484, 488, 112, 140):
    mutant = bytearray(data[:736])
    mutant[location] ^= 1
    try:
        check(mutant, generation['records'][0], generation['vectorRecords'][0])
    except AssertionError:
        pass
    else:
        raise AssertionError('Queue/type/owner/MSR/context-state mutant accepted')
ghidra_evidence = {}
for directory in ('dolphin-si-irq', 'ios-exception-vector', 'ios-irq-dispatch', 'ios-load-context'):
    path = Path('work/private-game/static-recomp') / directory / 'ghidra/verification.json'
    proof = json.loads(path.read_text())
    for row in proof['records']:
        assert row['assemblySha256'] == sha(path.parent / (row['name'] + '.asm'))
        assert row['decompiledSha256'] == sha(path.parent / (row['name'] + '.c'))
    ghidra_evidence[directory] = sha(path)
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_CPU_SI_QUEUE16_ALL4_TYPES8_EMPTY_QUEUE_CONTEXT_RETURN_PASS',
    'generationSha256': sha(generation_path), 'captureSha256': sha(capture_path), 'verifierSha256': sha(Path(__file__)),
    'parentVerifierSha256': sha(parent), 'states': states, 'ghidraEvidence': ghidra_evidence,
    'limits': generation['limits'] + ['Final endpoints and saved SRR wait range, not cycle-exact hardware/callback chronology.',
        'CPU GPR save overwrites prior context fields normally; this is not proof arbitrary populated FPU restoration.']}, indent=2) + '\n')
print('PASS16original CPU-delivered queued SI groups:64types completed/queue empty/callback cleared/populatedcontext owner/return')

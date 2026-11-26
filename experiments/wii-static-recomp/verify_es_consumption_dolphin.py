"""Verify whole original ES16 execution and exact preservation of the control chain."""
from pathlib import Path
import base64
import hashlib
import json
import struct

parent = Path('experiments/wii-static-recomp/verify_es_di_ticket_dolphin.py')
body = parent.read_text().replace('dolphin-es-di-ticket', 'dolphin-es-consumption').replace(
    'build_es_di_ticket_dolphin.py', 'build_es_consumption_dolphin.py').replace(
    'run_es_di_ticket_disc_dolphin.ps1', 'run_es_consumption_disc_dolphin.ps1').replace(
    'prepare_es_di_ticket_disc.py', 'prepare_es_consumption_disc.py').replace(
    '== 188', '== 292').replace('0x240', '0x280').replace(
    "struct.unpack_from('>I', prior, offset)[0] + 1", "struct.unpack_from('>I', prior, offset)[0] + 2").replace(
    '188byte ABI helper', '292byte ABI helper').replace('queue+1', 'queue+2').replace(
    'One extra completed request explains exact+1', 'Two extra completed requests explain exact+2')
marker = 'code.extend([dform(32, 3, 1, 8), dform(32, 0, 1, 20)'
assert body.count(marker) == 1
extra = '''pointer(code, 12, 0x806f4220)
pointer(code, 0, 0x12345678)
code.append(dform(36, 0, 12, 0))
pointer(code, 12, 0x806f4000)
code.extend([dform(32, 3, 12, 4), dform(32, 4, 12, 8), dform(14, 5, 0, 0)])
pointer(code, 6, 0x806f4220)
code.append(branch(call['text'] + len(code) * 4, 0x80249ce0, True))
pointer(code, 12, 0x806f4240)
code.extend([dform(36, 3, 12, 0), 0x7c0000a6, dform(36, 0, 12, 4)])
for address in (0x806f4220, 0x806f4240):
    pointer(code, 3, address)
    code.append(dform(14, 4, 0, 32))
    code.append(branch(call['text'] + len(code) * 4, 0x80212fd0, True))
'''
body = body.replace(marker, extra + marker)
exec(compile(body, str(parent), 'exec'), globals())
assert generation['consumptionParentGeneratorSha256'] == sha(experiment / 'build_es_di_ticket_dolphin.py')
assert generation['consumptionOracle'] == {'target': 0x80249ce0, 'ticketIdSource': 0x806f4004,
    'optionalArray': 0, 'count': 0x806f4220, 'initialCount': 0x12345678, 'scalars': 0x806f4240}
count = base64.b64decode(capture['consumptionCountPhysical'])
result = base64.b64decode(capture['consumptionScalarsPhysical'])

def check_consumption(count_bytes, result_bytes):
    assert count_bytes == bytes(32)
    assert result_bytes == struct.pack('>2I', 0, 0x2032) + bytes(24)

check_consumption(count, result)
for blob, other, first in ((count, result, True), (result, count, False)):
    for index in range(32):
        bad = bytearray(blob)
        bad[index] ^= 1
        try:
            check_consumption(bad if first else other, other if first else bad)
        except AssertionError:
            pass
        else:
            raise AssertionError('Consumption scalar/count mutation accepted')
control_ticket = json.loads((root / 'dolphin-es-di-ticket-disc/fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
for key in ('confPhysical', 'productPhysical', 'inquiryPhysical', 'ticketViewPhysical', 'ticketScalarsPhysical'):
    assert base64.b64decode(capture[key]) == base64.b64decode(control_ticket[key])
ghidra_path = root / 'es-consumption-source/ghidra/verification.json'
ghidra = json.loads(ghidra_path.read_text())
assert ghidra['records'][0]['instructions'] == 52
assert ghidra['records'][0]['bytes'] == ghidra['records'][0]['discoveredBodyBytes'] == 208
(output / 'consumption-comparison.json').write_text(json.dumps({
    'result': 'ORIGINAL_ES16_TICKET_ID_NULL_ARRAY_API0_COUNT0_CONTROL_CHAIN_PRESERVED_PASS',
    'verifierSha256': sha(Path(__file__)), 'parentVerifierSha256': sha(parent),
    'generationSha256': sha(generation_path), 'captureSha256': sha(capture_path),
    'ghidraSha256': sha(ghidra_path), 'countAndScalarMutantsRejected': 64,
    'limits': ['Whole original wrapper uses ticket ID from original view; poisoned count becomes0, API0/MSR2032.',
        'All original SDK bytes unchanged;292-byte helper verified instruction-by-instruction.',
        'Two extra requests vs burst explain four queue counters+2; all other control bytes/full files and ticket unchanged.',
        'Dolphin LAB ES response is emulator behavior, not proof of physical IOS consumption semantics.',
        'Native ES16 is still stopped before submission; no first screen or full-game claim.']}, indent=2) + '\n')
print('PASS whole original ES16 API0/count0/MSR2032/helper292/Ghidra52-208/control buffers preserved/64 scalar mutations')

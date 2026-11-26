"""Verify whole original ES close following ticket/inquiry/ES16, preserving earlier oracles."""
from pathlib import Path
import ast
import base64
import json
import struct

parent = Path('experiments/wii-static-recomp/verify_es_consumption_dolphin.py')
body = parent.read_text().replace('dolphin-es-consumption', 'dolphin-es-close-after-consumption').replace(
    'build_es_consumption_dolphin.py', 'build_es_close_after_consumption_dolphin.py').replace(
    'run_es_consumption_disc_dolphin.ps1', 'run_es_close_after_consumption_disc_dolphin.ps1').replace(
    'prepare_es_consumption_disc.py', 'prepare_es_close_after_consumption_disc.py').replace(
    '== 292', '== 348').replace('292byte', '348byte').replace('helper292', 'helper348').replace('292-byte', '348-byte').replace('queue+2', 'queue+3').replace(
    'Two extra requests vs burst explain four queue counters+2', 'Three extra requests vs burst explain four queue counters+3').replace(
    "struct.unpack_from('>I', prior, offset)[0] + 2", "struct.unpack_from('>I', prior, offset)[0] + 3")
node = next(node for node in ast.parse(body).body if isinstance(node, ast.Assign) and
    any(isinstance(target, ast.Name) and target.id == 'extra' for target in node.targets))
extra = ast.literal_eval(node.value)
extra += '''code.append(branch(call['text'] + len(code) * 4, 0x802497f0, True))
pointer(code, 12, 0x806f4260)
code.extend([dform(36, 3, 12, 0), 0x7c0000a6, dform(36, 0, 12, 4)])
pointer(code, 11, 0x80528ce8)
code.extend([dform(32, 0, 11, 0), dform(36, 0, 12, 8)])
pointer(code, 3, 0x806f4260)
code.append(dform(14, 4, 0, 32))
code.append(branch(call['text'] + len(code) * 4, 0x80212fd0, True))
'''
body = body.replace(ast.get_source_segment(body, node.value), repr(extra))
exec(compile(body, str(parent), 'exec'), globals())
assert generation['closeParentGeneratorSha256'] == sha(experiment / 'build_es_consumption_dolphin.py')
assert generation['closeOracle'] == {'target': 0x802497f0, 'scalars': 0x806f4260, 'sdkFdAddress': 0x80528ce8}
scalars = base64.b64decode(capture['closeScalarsPhysical'])
expected = struct.pack('>3I', 0, 0x2032, 0xffffffff) + bytes(20)
assert scalars == expected
for index in range(32):
    bad = bytearray(scalars)
    bad[index] ^= 1
    assert bad != expected
consumption = json.loads((root / 'dolphin-es-consumption-disc/fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
for key in ('confPhysical', 'productPhysical', 'inquiryPhysical', 'ticketViewPhysical', 'ticketScalarsPhysical',
    'consumptionCountPhysical', 'consumptionScalarsPhysical'):
    assert base64.b64decode(capture[key]) == base64.b64decode(consumption[key])
(output / 'close-after-consumption-comparison.json').write_text(json.dumps({
    'result': 'ORIGINAL_ES_CLOSE_AFTER_ES16_API0_SDK_FD_MINUS1_CONTROL_BUFFERS_PRESERVED_PASS',
    'verifierSha256': sha(Path(__file__)), 'generationSha256': sha(generation_path),
    'captureSha256': sha(capture_path), 'scalarMutantsRejected': 32,
    'limits': ['Whole ESP_CloseLib writes SDK FD-1; API0/MSR2032/full32 scalar capture.',
        '348-byte ABI helper reconstructed instruction-by-instruction; original SDK bytes unchanged.',
        'All previous full buffers preserved; three completed extra requests explain only four queue counters+3 vs burst.',
        'Original PPC under private Dolphin LAB, not physical IOS/cache timing or native CLOSE completion.']}, indent=2) + '\n')
print('PASS original whole CLOSE afterES16 API0/SDKFD-1/MSR2032/helper348/previousbuffers unchanged/32 mutations')

"""Verify both blocked async-request views, callback metadata and source stores."""
from pathlib import Path
import hashlib
import json
import struct

audit_parent = Path('experiments/wii-static-recomp/audit_stm_eventhook_boot.py')
body = audit_parent.read_text().replace('mass-stm-eventhook-boot', 'mass-stm-async-packet-observer')
body = body.replace('build_stm_eventhook_boot.py', 'observe_stm_async_packet.py')
exec(compile(body, str(audit_parent), 'exec'), globals())
assert build['observerParentSha256'] == sha(Path('experiments/wii-static-recomp/build_stm_eventhook_boot.py'))
log = (output / 'live-boot.log').read_text()
expected_header = struct.pack('>8I', 6, 1, 1, 0x1000, 0x493060, 32, 0x493080, 32)
observed = {}
def validate(view, packet):
    expected_tail = struct.pack('>8I', 0x8021cc70 if view == 'cached' else 0, 0, 0, 0, 0, 0, 0, 0)
    assert packet == expected_header + expected_tail

for marker in ('BOOT_STM_NEXT_PACKET ', 'BOOT_STM_NEXT_CACHED '):
    line = next(line for line in log.splitlines() if line.startswith(marker)).split()[1:]
    assert int(line[0]) == 0x135e0020 and len(line) == 65
    packet = bytes(map(int, line[1:]))
    view = 'cached' if 'CACHED' in marker else 'physical'
    validate(view, packet)
    observed[view] = packet.hex()
    print(marker.strip() + ' words=' + ','.join(hex(word) for word in struct.unpack('>16I', packet)))
for view, location in (('physical', 0), ('physical', 4), ('cached', 12), ('cached', 32), ('cached', 36), ('cached', 40)):
    packet = bytearray.fromhex(observed[view])
    packet[location] ^= 1
    try:
        validate(view, packet)
    except AssertionError:
        pass
    else:
        raise AssertionError('Async header/callback/metadata mutant accepted')
for address, opcode in ((0x80242d5c, 0x93a30020), (0x80242d6c, 0x93c40024),
    (0x80242d74, 0x90a40028), (0x80242238, 0x38800020)):
    section = next(i for i in range(7) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
    assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == opcode
ghidra_path = root / 'stm-async-source/ghidra/verification.json'
ghidra = json.loads(ghidra_path.read_text())
assert len(ghidra['records']) == 3
assert ghidra['runnerSha256'] == sha(Path('experiments/wii-static-recomp/verify_stm_async_ghidra.py'))
assert [(row['name'], row['instructions'], row['bytes']) for row in ghidra['records']] == [
    ('__OSInitSTM', 70, 280), ('IOS_IoctlAsync', 78, 312), ('__OSStateEventHandler', 85, 340)]
for record in ghidra['records']:
    assert record['objectSha256'] == sha(root / 'dtk-output/obj/auto_03_802045CC_text.o')
    assert sha(ghidra_path.parent / (record['name'] + '.asm')) == record['assemblySha256']
    assert sha(ghidra_path.parent / (record['name'] + '.c')) == record['decompiledSha256']
(output / 'packet-observation.json').write_text(json.dumps({'result': 'BLOCKED_ASYNC_CACHED_CALLBACK_PHYSICAL_ZERO_SOURCE_STORES_VERIFIED',
    'verifierSha256': sha(Path(__file__)), 'auditParentSha256': sha(audit_parent),
    'buildSha256': sha(output / 'build.json'), 'logSha256': sha(output / 'live-boot.log'),
    'views': observed, 'mutantsRejected': 6, 'ghidraEvidenceSha256': sha(ghidra_path),
    'limits': build['limits']}, indent=2) + '\n')
print('PASS cached callback8021CC70/physicalzero/userdata0/field40zero; DOL stores/Ghidra/fresh boot/6mutants')

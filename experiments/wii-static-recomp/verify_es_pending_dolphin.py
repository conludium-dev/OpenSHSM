"""Verify whole original ESP_InitLib return, FD store, reply and retained STM."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_fs_pending_dolphin.py')
body = parent.read_text().replace('dolphin-fs-pending', 'dolphin-es-pending')
body = body.replace('build_fs_pending_dolphin.py', 'build_es_pending_dolphin.py').replace('run_fs_pending_dolphin.ps1', 'run_es_pending_dolphin.ps1')
body = body.replace('[0x80242550] * 13', '[0x80242550, 0x80249790] + [0x80242550] * 11')
body = body.replace('result = index - 1 if index < 10 else -6', 'result = 2 if index == 3 else 0 if index == 4 else -6')
body = body.replace("reply = struct.pack('>5I', 8, result & 0xffffffff, 1, 0x135e1000, 0) + bytes(44)",
    "reply = struct.pack('>5I', 8, 3 if index == 4 else result & 0xffffffff, 1, 0x528cf0 if index == 4 else 0x135e1000, 0) + bytes(44)")
old = "    assert row[576:640] == (case['fsPath'].encode() + b'\\0').ljust(64, b'\\0')"
new = '''    if index == 4:
        section = next(i for i in range(18) if layout[18 + i] <= 0x80528cf0 and 0x80528d30 <= layout[18 + i] + layout[36 + i])
        offset = layout[section] + 0x80528cf0 - layout[18 + section]
        assert row[576:640] == original[offset:offset + 64] and row[576:584] == b'/dev/es\\0'
    else:
        assert row[576:640] == (case['fsPath'].encode() + b'\\0').ljust(64, b'\\0')
    assert struct.unpack_from('>I', row, 640)[0] == (0xffffffff if index == 3 else 3)
'''
assert body.count(old) == 1
body = body.replace(old, new)
body = body.replace('ORIGINAL_FS_OPEN7_FD2_TO8_MISSING6_PENDING_STM_AND_HEAP_PRESERVED', 'ORIGINAL_ESP_INIT_RETURNS0_STORES_FD3_AFTER_FS_PENDING_STM_RETAINED')
body = body.replace('PASS original whole IOS_Open: FS7 FD2..8, missing6=-6; both64 replies, heap reuse, STM pending retained;19mutants',
    'PASS original ESP_InitLib returns0/storesFD3 afterFS2; missing11=-6, both64 replies/pendingSTM/heap retained;19mutants')
namespace = {'__file__': __file__}
exec(compile(body, str(parent), 'exec'), namespace)
globals().update(namespace)
assert generation['esParentSha256'] == sha(experiment / 'build_fs_pending_dolphin.py')
proof_path = root / 'es-init-source/ghidra/verification.json'
proof = json.loads(proof_path.read_text())
assert proof['runnerSha256'] == sha(experiment / 'verify_es_init_ghidra.py')
record = proof['records'][0]
assert record['name'] == 'ESP_InitLib' and record['instructions'] == 21 and record['bytes'] == 84
assert record['assemblySha256'] == sha(proof_path.parent / 'ESP_InitLib.asm')
assert record['decompiledSha256'] == sha(proof_path.parent / 'ESP_InitLib.c')
section = next(i for i in range(7) if layout[18 + i] <= 0x802497b8 < layout[18 + i] + layout[36 + i])
assert struct.unpack_from('>I', original, layout[section] + 0x802497b8 - layout[18 + section])[0] == 0x4bff8d99
path = output / 'comparison.json'
report = json.loads(path.read_text())
for location in locations + [640]:
    mutant = bytearray(data[2944:3680])
    mutant[location] ^= 1
    try:
        check_fs(mutant, generation['records'][4])
    except AssertionError:
        pass
    else:
        raise AssertionError('ESP return/FD/reply/pending mutant accepted')
report['mutantsRejected'] = len(locations) * 2 + 1
report['esGhidraEvidenceSha256'] = sha(proof_path)
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS additional20 ESP return/FD/reply/pending mutations;39 total')

"""Validate the original standalone-context title-query error without inventing a retail title ID."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_es_pending_dolphin.py')
body = parent.read_text().replace('dolphin-es-pending', 'dolphin-es-title')
body = body.replace('build_es_pending_dolphin.py', 'build_es_title_dolphin.py').replace('run_es_pending_dolphin.ps1', 'run_es_title_dolphin.ps1')
body = body.replace('[0x80242550] * 11', '[0x80249c40] * 11')
marker = "namespace = {'__file__': __file__}"
assert body.count(marker) == 1
body = body.replace(marker, "body = body.replace('for i in range(3, 16)', 'for i in range(3, 5)')\n" + marker)
body = body.replace('PASS original ESP_InitLib returns0/storesFD3 afterFS2; missing11=-6, both64 replies/pendingSTM/heap retained;19mutants',
    'PASS initial original FS2/ESP_InitLib0-FD3/pending STM before title-query cases')
namespace = {'__file__': __file__}
exec(compile(body, str(parent), 'exec'), namespace)
globals().update(namespace)
assert generation['titleParentSha256'] == sha(experiment / 'build_es_pending_dolphin.py')
proof_path = root / 'es-vector-source/ghidra/verification.json'
proof = json.loads(proof_path.read_text())
assert proof['runnerSha256'] == sha(experiment / 'verify_es_vector_ghidra.py')
for record in proof['records']:
    assert record['assemblySha256'] == sha(proof_path.parent / (record['name'] + '.asm'))
    assert record['decompiledSha256'] == sha(proof_path.parent / (record['name'] + '.c'))

def check_title(row, case):
    index = case['index']
    assert case['kind'] == 'ESP_GetTitleId'
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    count = index + 2
    state = list(struct.unpack_from('>22I', row, 24))
    assert state == [0x38, 0x135e0080, 0x10000, 1, 0, 0, 0, 0x80492658, 0x80492658, 0x492658,
        0x80492658, 0x20001, 0, 0x935e0060, 0x50, count, count, count & 15, count & 15, 0x8021a890, 0x2032, 0xa032]
    assert row[192:256].hex() == pending['physicalPacketHex'] and row[256:320].hex() == pending['cachedPacketHex']
    assert struct.unpack_from('>2I', row, 400) == (0xfffffc07, 0xa032)
    physical = struct.pack('>8I', 8, 0xfffffc07, 7, 0x20, 0, 1, 0x53ffb0, 0) + bytes(32)
    cached = struct.pack('>8I', 8, 0xfffffc07, 7, 0x20, 0, 1, 0x8053ffb0, 0) + bytes(32)
    assert row[448:512] == physical and row[512:576] == cached
    assert row[576:608] == bytes(32) and row[608:640] == bytes([0xa5]) * 32
    assert row[656:672] == bytes([0xb6]) * 16
    assert struct.unpack_from('>4I', row, 672) == (0x8053fee0, 8, 0x53fee0, 8)
    assert struct.unpack_from('>I', row, 640)[0] == 3 and row[416:448] == bytes(32)
    return {'index': index, 'returnValue': -1017, 'states': state, 'physicalReplyHex': physical.hex(),
        'cachedReplyHex': cached.hex(), 'callerPhysicalHex': row[576:608].hex(), 'callerCachedHex': row[608:640].hex(),
        'temporaryCachedHex': row[656:664].hex(), 'temporaryPhysicalHex': row[664:672].hex(),
        'vectorCachedHex': row[672:680].hex(), 'vectorPhysicalHex': row[680:688].hex()}

title_cases = [check_title(data[i * 736:(i + 1) * 736], generation['records'][i]) for i in range(5, 16)]
locations = [24, 28, 80, 84, 108, 192, 288, 400, 404, 416, 448, 452, 472, 512, 536, 576, 608, 640, 656, 664, 672, 680]
for location in locations:
    mutant = bytearray(data[3680:4416])
    mutant[location] ^= 1
    try:
        check_title(mutant, generation['records'][5])
    except AssertionError:
        pass
    else:
        raise AssertionError('Wrong error/zeroed caller/temporary/vector/pending reply accepted')
path = output / 'comparison.json'
report = json.loads(path.read_text())
report['result'] = 'ORIGINAL_STANDALONE_TITLE_QUERY11_ERROR_MINUS1017_CALLER_TEMPORARY_UNCHANGED_PENDING_STM'
report['titleCases'] = title_cases
report['titleMutantsRejected'] = len(locations)
report['titleVectorGhidraEvidenceSha256'] = sha(proof_path)
report['limits'] = generation['limits'] + ['The eleven -1017 results prove this isolated emulator error path only, NOT the response of supported retail Wii SHSM.',
    'Caller cache A5 vs physical zero was intentionally not flushed; temporary B6 retained, vector cached virtual/physical-address views differ correctly.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS original standalone ESP_GetTitleId11 returns-1017, preserves caller/temp/vector/cache/STM;22mutants. Retail title response UNVERIFIED')

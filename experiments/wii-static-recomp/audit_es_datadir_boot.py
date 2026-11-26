"""Compare native GetDataDir continuation to the measured own-disc original contract."""
from pathlib import Path
import hashlib
import json
import os
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'mass-es-datadir-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
base_path = root / 'mass-es-title-boot/build.json'
base = json.loads(base_path.read_text())
assert build['builderSha256'] == sha(experiment / 'build_es_datadir_boot.py')
assert build['parentBuilderSha256'] == sha(experiment / 'build_fs_open_boot.py')
assert build['baseBuildSha256'] == sha(base_path)
assert build['adapterSha256'] == sha(experiment / 'es_datadir_adapter.h')
tmd = Path('work/private-game/disc/DATA/tmd.bin')
assert build['tmdSha256'] == sha(tmd)
title = tmd.read_bytes()[0x18c:0x194]
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
assert len(build['records']) == 125
assert [row['file'] for row, old in zip(build['records'], base['records']) if row != old] == [
    'output_62.cpp', 'output_63.cpp', 'output_67.cpp']
for row, old in zip(build['records'], base['records']):
    assert row['sourceSha256'] == old['sourceSha256']
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
oracle_path = root / 'dolphin-es-datadir-disc/disc-comparison.json'
oracle = json.loads(oracle_path.read_text())
assert oracle['result'] == 'ORIGINAL_DISC_GETDATADIR10_OUTPUT29_NO_NUL_GUARDS3_PENDING_STM_PASS'
original_case = oracle['cases'][0]
expected_path = original_case['path'].encode('ascii')
assert original_case['outputBytesWritten'] == len(expected_path) == 29 and not original_case['terminatorWritten']
pending = json.loads((root / 'dolphin-es-pending/comparison.json').read_text())['initialPending']
exe = output / 'openshsm-mass-boot'
assert sha(exe) == build['executableSha256']


def check(lines, enabled):
    def tokens(prefix):
        matches = [line for line in lines if line.startswith(prefix + ' ')]
        assert len(matches) == 1, prefix
        return matches[0].split()[1:]

    def bytes_at(prefix):
        return bytes(map(int, tokens(prefix)))

    assert 'BOOT_FS_REPLY 2 935e0060 50' in lines and 'BOOT_ES_REPLY 3 935e0060 50' in lines
    title_before, title_after = tokens('BOOT_TITLE_BEFORE'), tokens('BOOT_TITLE_AFTER')
    assert title_before[0] == title_after[0]
    assert bytes(map(int, title_after[1:9])) == title
    assert title_before[9:] == title_after[9:]
    assert tokens('BOOT_DATADIR_ARGS') == [format(int.from_bytes(title[:4], 'big'), 'x'),
        format(int.from_bytes(title[4:], 'big'), 'x'), '804b2cc0']
    before = bytes_at('BOOT_DATADIR_BEFORE')
    assert len(before) == 32
    for view, key in (('PHYSICAL', 'physicalPacketHex'), ('CACHED', 'cachedPacketHex')):
        assert bytes_at('BOOT_STM_ASYNC_' + view).hex() == pending[key]
    assert 'BOOT_STM_ASYNC dispatched=1 pending=1 6 1 324927520 4096 4796512 32 4796544 32' in lines
    boundary = ' '.join(tokens('BOOT_BOUNDARY'))
    if enabled:
        assert tokens('BOOT_DATADIR_CONTINUATION') == ['8019d564', '8024635c']
        assert 'BOOT_DATADIR_HEAP 935e0060 50' in lines
        for view, key, vector in (('PHYSICAL', 'physicalReplyHex', 0x540010),
                                  ('CACHED', 'cachedReplyHex', 0x80540010)):
            expected = bytearray.fromhex(original_case[key])
            struct.pack_into('>I', expected, 24, vector)
            assert bytes_at('BOOT_DATADIR_REPLY_' + view) == expected
            assert bytes_at('BOOT_DATADIR_INPUT_' + view) == title
            result = bytes_at('BOOT_DATADIR_OUTPUT_' + view)
            assert result[:29] == expected_path and result[29:] == before[29:]
        assert struct.unpack('>4I', bytes_at('BOOT_DATADIR_VECTOR_PHYSICAL')) == (0x53ff40, 8, 0x4b2cc0, 30)
        assert struct.unpack('>4I', bytes_at('BOOT_DATADIR_VECTOR_CACHED')) == (0x8053ff40, 8, 0x804b2cc0, 30)
        assert 'BOOT_STM submitted=14 produced=6' in lines and 'BOOT_SI_DELIVERY entries=17 callbacks=4' in lines
        assert 'BOOT_FLUSH entries=22 phase=0 barriers=16' in lines
        assert boundary.startswith('pc=80241c30 lr=80242384 msr=2032') and 'STM sender caller/value unverified' in boundary
        packet = tokens('BOOT_STM_NEXT_PACKET')
        assert int(packet[0]) == 0x135e0080
        assert struct.unpack_from('>8I', bytes(map(int, packet[1:]))) == (2, 0, 3, 0x1d, 1, 1, 0x80540010, 0)
    else:
        assert not any(line.startswith('BOOT_DATADIR_CONTINUATION ') for line in lines)
        assert 'BOOT_STM submitted=12 produced=5' in lines and 'BOOT_SI_DELIVERY entries=15 callbacks=4' in lines
        assert boundary.startswith('pc=80212ff4 lr=80242fc8 msr=a032')
        assert struct.unpack_from('>8I', bytes_at('BOOT_ES_NEXT_CACHED')) == (7, 0, 3, 0x1d, 1, 1, 0x80540010, 0)
    return boundary


results, logs = {}, {}
for mode in ('live', 'disabled'):
    env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
    env['SHSM_ES_TMD_PATH'] = str(tmd)
    if mode == 'disabled':
        env['SHSM_ES_DATADIR_DISABLED'] = '1'
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(output / 'boot-quarantine.tsv'),
        str(root / 'sram-native/settings.bin')], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 7 and not result.stderr
    path = output / (mode + '-boot.log')
    path.write_text(result.stdout)
    logs[mode] = result.stdout.splitlines()
    results[mode] = {'boundary': check(logs[mode], mode == 'live'), 'logSha256': sha(path)}
mutants = 0
for prefix, index in [('BOOT_DATADIR_OUTPUT_PHYSICAL', 1), ('BOOT_DATADIR_OUTPUT_CACHED', 30),
    ('BOOT_DATADIR_INPUT_PHYSICAL', 1), ('BOOT_DATADIR_INPUT_CACHED', 1), ('BOOT_DATADIR_VECTOR_PHYSICAL', 1),
    ('BOOT_DATADIR_VECTOR_CACHED', 1), ('BOOT_DATADIR_REPLY_PHYSICAL', 1), ('BOOT_DATADIR_REPLY_CACHED', 1),
    ('BOOT_STM_ASYNC_CACHED', 33)]:
    changed = list(logs['live'])
    slot = next(i for i, line in enumerate(changed) if line.startswith(prefix + ' '))
    parts = changed[slot].split()
    parts[index] = str(int(parts[index]) ^ 1)
    changed[slot] = ' '.join(parts)
    try:
        check(changed, True)
    except AssertionError:
        mutants += 1
assert mutants == 9
(output / 'audit.json').write_text(json.dumps({'result': 'NATIVE_FIRST_GETDATADIR_ORIGINAL29_SOURCE_CONTINUATION_PASS',
    'verifierSha256': sha(Path(__file__)), 'buildSha256': sha(output / 'build.json'), 'oracleSha256': sha(oracle_path),
    'results': results, 'rejectedObservationMutants': mutants,
    'limits': ['Oracle input/vector/output addresses explicitly relocated for native SDK stack/BSS. Oracle guards A5, native BSS tail zero preserved.',
        'Observed original SDK under Dolphin IOS and native PC service/event adapters, not physical Wii/full retail equivalence or save-file IO.']}, indent=2) + '\n')
print('PASS native GetDataDir29/no added NUL/guard3/input2vectors/both64 replies/heap/STM/disabled;9mutants; next CLOSE refused')

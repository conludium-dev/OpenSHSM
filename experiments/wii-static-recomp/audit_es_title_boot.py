"""Compare the first native title reply/source copy against the own-disc SDK oracle."""
from pathlib import Path
import hashlib
import json
import os
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'mass-es-title-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
base_path = root / 'mass-es-open-boot/build.json'
base = json.loads(base_path.read_text())
assert build['builderSha256'] == sha(experiment / 'build_es_title_boot.py')
assert build['parentBuilderSha256'] == sha(experiment / 'build_fs_open_boot.py')
assert build['baseBuildSha256'] == sha(base_path)
assert build['adapterSha256'] == sha(experiment / 'es_title_adapter.h')
tmd_path = Path('work/private-game/disc/DATA/tmd.bin')
assert build['tmdSha256'] == sha(tmd_path)
title = tmd_path.read_bytes()[0x18c:0x194]
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
assert len(build['records']) == 125
assert [row['file'] for row, old in zip(build['records'], base['records']) if row != old] == [
    'output_62.cpp', 'output_63.cpp', 'output_67.cpp']
for row, old in zip(build['records'], base['records']):
    assert row['sourceSha256'] == old['sourceSha256']
    assert sha(Path(row['source'])) == row['sourceSha256']
    assert sha(Path(row['object'])) == row['objectSha256']
oracle_path = root / 'dolphin-es-disc/disc-comparison.json'
oracle = json.loads(oracle_path.read_text())
pending = json.loads((root / 'dolphin-es-pending/comparison.json').read_text())['initialPending']
exe = output / 'openshsm-mass-boot'
assert sha(exe) == build['executableSha256']


def validate(lines, enabled):
    def values(prefix):
        matches = [line for line in lines if line.startswith(prefix + ' ')]
        assert len(matches) == 1, prefix
        return matches[0].split()[1:]

    for view, key in (('PHYSICAL', 'physicalPacketHex'), ('CACHED', 'cachedPacketHex')):
        assert bytes(map(int, values('BOOT_STM_ASYNC_' + view))).hex() == pending[key]
    assert 'BOOT_STM_ASYNC dispatched=1 pending=1 6 1 324927520 4096 4796512 32 4796544 32' in lines
    assert 'BOOT_FS_REPLY 2 935e0060 50' in lines and 'BOOT_ES_REPLY 3 935e0060 50' in lines
    before = values('BOOT_TITLE_BEFORE')
    boundary = ' '.join(values('BOOT_BOUNDARY'))
    assert boundary.startswith('pc=80212ff4 lr=80242fc8 msr=a032')
    assert 'EE flush caller/pending-state unverified' in boundary
    cached_next = bytes(map(int, values('BOOT_ES_NEXT_CACHED')))
    if enabled:
        after = values('BOOT_TITLE_AFTER')
        assert before[0] == after[0]
        before_bytes, after_bytes = bytes(map(int, before[1:])), bytes(map(int, after[1:]))
        assert len(after_bytes) == 32 and after_bytes[:8] == title
        assert after_bytes[8:] == before_bytes[8:]
        assert values('BOOT_TITLE_CAPTURE_AT') == ['80249ba0']
        assert 'BOOT_TITLE_HEAP 935e0060 50' in lines
        assert 'BOOT_STM submitted=12 produced=5' in lines
        assert 'BOOT_SI_DELIVERY entries=15 callbacks=4' in lines
        assert 'BOOT_FLUSH entries=17 phase=0 barriers=11' in lines
        for view, key, vector in (('PHYSICAL', 'physicalReplyHex', 0x53fff0),
                                  ('CACHED', 'cachedReplyHex', 0x8053fff0)):
            reply = bytes(map(int, values('BOOT_TITLE_REPLY_' + view)))
            expected = bytearray.fromhex(oracle['cases'][0][key])
            struct.pack_into('>I', expected, 24, vector)
            assert reply == expected
            temp = bytes(map(int, values('BOOT_TITLE_TEMP_' + view)))
            assert len(temp) == 32 and temp[:8] == title and temp[8:] == bytes(24)
        assert struct.unpack_from('>8I', cached_next) == (7, 0, 3, 0x1d, 1, 1, 0x80540010, 0)
    else:
        assert not any(line.startswith('BOOT_TITLE_AFTER ') for line in lines)
        assert 'BOOT_STM submitted=10 produced=4' in lines
        assert 'BOOT_SI_DELIVERY entries=13 callbacks=4' in lines
        assert struct.unpack_from('>8I', cached_next) == (7, 3, 3, 0x20, 0, 1, 0x8053fff0, 0)
    return boundary


results = {}
logs = {}
for mode in ('live', 'disabled'):
    env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
    env['SHSM_ES_TMD_PATH'] = str(tmd_path)
    if mode == 'disabled':
        env['SHSM_ES_TITLE_DISABLED'] = '1'
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(output / 'boot-quarantine.tsv'),
        str(root / 'sram-native/settings.bin')], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 7 and not result.stderr
    path = output / (mode + '-boot.log')
    path.write_text(result.stdout)
    logs[mode] = result.stdout.splitlines()
    results[mode] = {'boundary': validate(logs[mode], mode == 'live'), 'logSha256': sha(path)}
mutants = 0
for prefix in ('BOOT_TITLE_AFTER', 'BOOT_TITLE_REPLY_PHYSICAL', 'BOOT_TITLE_REPLY_CACHED',
               'BOOT_TITLE_TEMP_PHYSICAL', 'BOOT_TITLE_TEMP_CACHED', 'BOOT_STM_ASYNC_CACHED'):
    changed = list(logs['live'])
    index = next(i for i, line in enumerate(changed) if line.startswith(prefix + ' '))
    parts = changed[index].split()
    offset = 2 if prefix == 'BOOT_TITLE_AFTER' else 1
    parts[offset] = str(int(parts[offset]) ^ 1)
    changed[index] = ' '.join(parts)
    try:
        validate(changed, True)
    except AssertionError:
        mutants += 1
assert mutants == 6
(output / 'audit.json').write_text(json.dumps({'result': 'NATIVE_FIRST_ES_TITLE_SOURCE_COPY_ORIGINAL_DISC_REPLY_PASS',
    'verifierSha256': sha(Path(__file__)), 'buildSha256': sha(output / 'build.json'),
    'oracleSha256': sha(oracle_path), 'results': results, 'rejectedObservationMutants': mutants,
    'limits': ['First IOCTLV20 only; oracle/native vector and temporary stack addresses differ by disclosed frame relocation.',
        'Existing event delivery timing and IOS metadata service are PC adaptations, not physical Wii or complete game boot.']}, indent=2) + '\n')
print('PASS first native title8/source copy/guards24/both64 replies/heap/pending/disabled;6 observation mutants; nextcmd1D refused')

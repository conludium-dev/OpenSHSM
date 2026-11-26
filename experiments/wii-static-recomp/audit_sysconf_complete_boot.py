"""Verify whole native SC completion, original replies/free order and full console buffers."""
from pathlib import Path
import base64
import hashlib
import json
import os
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'mass-sysconf-complete-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
base_path = root / 'mass-sysconf-product-boot/build.json'
base = json.loads(base_path.read_text())
assert build['builderSha256'] == sha(experiment / 'build_sysconf_complete_boot.py')
assert base['builderSha256'] == sha(experiment / 'build_sysconf_product_boot.py')
assert build['baseBuildSha256'] == sha(base_path)
assert build['parentBuilderSha256'] == sha(experiment / 'build_fs_open_boot.py')
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
assert len(build['records']) == 125
assert [row['file'] for row, old in zip(build['records'], base['records']) if row != old] == [
    'output_62.cpp', 'output_63.cpp', 'output_67.cpp', 'output_68.cpp']
for row, old in zip(build['records'], base['records']):
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    if row['file'] == 'output_68.cpp':
        added = '\n    nwii::runtime::experiment_sc_status_observe(ctx);'
        text = Path(row['source']).read_text()
        assert text.count(added) == 1 and text.replace(added, '') == Path(old['source']).read_text()
    else:
        assert row['sourceSha256'] == old['sourceSha256']
for name in ('stm_device.cpp', 'es_device.cpp', 'fs_device.cpp'):
    assert sha(output / name) == sha(base_path.parent / name)
oracle_path = root / 'dolphin-sysconf-events-fixed-disc/fpr-init-true-dolphin.json'
oracle = json.loads(oracle_path.read_text(encoding='utf-8-sig'))
raw = base64.b64decode(oracle['events'])
events = [raw[64 + i * 1280:64 + (i + 1) * 1280] for i in range(115)]
product_path = root / 'dolphin-sysconf-product-oracle-disc/fpr-init-true-dolphin.json'
product_oracle = json.loads(product_path.read_text(encoding='utf-8-sig'))
data = base64.b64decode(product_oracle['data'])[15 * 736:16 * 736]
conf = base64.b64decode(product_oracle['confPhysical'])
product = base64.b64decode(product_oracle['productPhysical'])
cache_path = root / 'dolphin-sysconf-cache-oracle-disc/fpr-init-true-dolphin.json'
cache_oracle = json.loads(cache_path.read_text(encoding='utf-8-sig'))
parsed = base64.b64decode(cache_oracle['parsedCache'])
assert len(parsed) == 16704 and parsed[:16] == b'OSHSM_SC_CACHE01'
assert hashlib.sha256(product).hexdigest() == build['laboratoryProductSha256']


def check(lines, enabled):
    def one(prefix):
        matches = [line[len(prefix) + 1:].split() for line in lines if line.startswith(prefix + ' ')]
        assert len(matches) == 1, prefix
        return matches[0]

    assert 'BOOT_STM_ASYNC dispatched=1 pending=1 6 1 324927520 4096 4796512 32 4796544 32' in lines
    assert one('SC_OPEN_API_RETURN') == ['0', 'a032', '1', '31']
    assert 'BOOT_ES_CLOSE_STATE ffffffff 935e0060 50' in lines
    boundary = ' '.join(one('BOOT_BOUNDARY'))
    if not enabled:
        assert 'BOOT_STM submitted=24 produced=11' in lines
        assert boundary.startswith('pc=80212ff4 lr=80242240 msr=32')
        assert not any(line.startswith('SC_STATUS_ORIGINAL_RETURN') or line.startswith('SC_TAIL_CALLBACK') for line in lines)
        return
    assert 'BOOT_STM submitted=28 produced=13' in lines
    assert 'BOOT_SI_DELIVERY entries=31 callbacks=4' in lines
    status = one('SC_STATUS_ORIGINAL_RETURN')
    assert list(map(lambda x: int(x, 16), status[:5])) == [struct.unpack_from('>I', data, i)[0] for i in (400, 404, 608, 612, 616)]
    assert status[5:] == ['935e0060', '50', 'e', 'e']
    assert struct.unpack_from('>I', data, 84)[0] == struct.unpack_from('>I', data, 96)[0] == 15
    assert list(map(lambda x: int(x, 16), one('SC_STATUS_FRAME'))) == [struct.unpack_from('>I', data, i)[0] for i in (720, 724, 728, 732, 708, 712, 716)]
    sequence = [line for line in lines if line.startswith(('SC_TAIL_FREE ', 'SC_TAIL_CALLBACK '))]
    assert sequence == ['SC_TAIL_FREE 1a 1 935e1180 32', 'SC_TAIL_FREE 1a 0 935e00e0 32',
        'SC_TAIL_CALLBACK 1a 80240680 100 935e1020 32', 'SC_TAIL_CALLBACK 1a 80247800 100 804b3094 32',
        'SC_TAIL_FREE 1c 1 935e1020 32', 'SC_TAIL_FREE 1c 0 935e0080 32',
        'SC_TAIL_CALLBACK 1c 80240680 0 935e1180 32', 'SC_TAIL_CALLBACK 1c 802478f0 0 804b3094 32',
        'SC_TAIL_FREE 1c 1 935e1180 32', 'SC_TAIL_FREE 1c 0 935e00e0 32']
    for index, count, address, offset in ((86, 'PRODUCT', '80240680', 192), (87, 'PRODUCT', '80244e30', 192),
        (88, 'PRODUCT', '80247730', 192), (98, '1a', '80240680', 64), (99, '1a', '80247800', 64),
        (110, '1c', '80240680', 192)):
        for view, delta in (('CACHED', 0), ('PHYSICAL', 64)):
            expected = bytearray(events[index][offset + delta:offset + delta + 64])
            if count == '1a':
                struct.pack_into('>I', expected, 24, 0x80540010)
            prefix = 'SC_PRODUCT_REPLY_' + view + ' ' + address if count == 'PRODUCT' else 'SC_TAIL_REPLY_' + view + ' ' + count + ' ' + address
            assert bytes(map(int, one(prefix))) == expected
    for view in ('CACHED', 'PHYSICAL'):
        assert bytes(map(int, one('SC_COMPLETE_PRODUCT_' + view))) == product
        assert bytes(map(int, one('SC_COMPLETE_CONF_' + view))) == (parsed[64:16448] if view == 'CACHED' else conf)
    assert boundary.startswith('pc=80241c30 lr=80242384 msr=2032')
    packet = bytes(map(int, one('SC_COMPLETE_NEXT_PACKET')))
    assert struct.unpack_from('>I', packet)[0] == 1
    assert bytes(map(int, one('SC_COMPLETE_NEXT_PATH'))) == b'/dev/di'.ljust(64, b'\0')


exe = output / 'openshsm-mass-boot'
assert sha(exe) == build['executableSha256']
observations = {}
for mode in ('live', 'disabled'):
    env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
    env['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'
    env['SHSM_SC_LAB_FILE'] = '_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF'
    env['SHSM_SC_LAB_PRODUCT'] = '_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt'
    if mode == 'disabled':
        env['SHSM_SC_PRODUCT_TAIL_DISABLED'] = '1'
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(output / 'boot-quarantine.tsv'),
        str(root / 'sram-native/settings.bin')], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 7 and not result.stderr
    (output / (mode + '-audit.log')).write_text(result.stdout)
    observations[mode] = result.stdout.splitlines()
    check(observations[mode], mode == 'live')
mutants = 0
for prefix in ('SC_STATUS_ORIGINAL_RETURN', 'SC_STATUS_FRAME', 'SC_COMPLETE_PRODUCT_CACHED', 'SC_COMPLETE_PRODUCT_PHYSICAL',
    'SC_COMPLETE_CONF_CACHED', 'SC_COMPLETE_CONF_PHYSICAL', 'SC_TAIL_FREE 1a 1', 'SC_TAIL_FREE 1c 0 935e00e0',
    'SC_TAIL_CALLBACK 1a 80247800', 'SC_TAIL_CALLBACK 1c 802478f0', 'SC_TAIL_REPLY_CACHED 1a 80240680',
    'SC_TAIL_REPLY_PHYSICAL 1c 80240680', 'SC_COMPLETE_NEXT_PATH', 'BOOT_STM_ASYNC dispatched='):
    try:
        check([line for line in observations['live'] if not line.startswith(prefix)], True)
    except AssertionError:
        mutants += 1
    else:
        raise AssertionError(prefix)
(output / 'audit.json').write_text(json.dumps({'verifierSha256': sha(Path(__file__)), 'buildSha256': sha(output / 'build.json'),
    'oracleSha256': sha(oracle_path), 'productOracleSha256': sha(product_path), 'cachedOracleSha256': sha(cache_path), 'mutants': mutants,
    'result': 'NATIVE_WHOLE_SC_ORIGINAL_STATUS0_PARSED_FRAME_FULL_FILES_CALLBACKS_FREES_PASS',
    'limits': ['Native queue14 vs oracle15: original fixture begins at1/native boot0; empty endpoints and request delta matched.',
        'SC-return heap0060 verified; next /dev/di request already allocated0080 at later stop/freehead00c0.',
        'Explicit private LAB files, DevKit fallback and PC event timing are not production settings/physical retail/cycle proof.']}, indent=2) + '\n')
print('PASS native wholeSC/sourceAPI0+flags+parsedframe/originalreplies/full16384+256buffers/free order/STM/disabled;14mutants;next /dev/di')

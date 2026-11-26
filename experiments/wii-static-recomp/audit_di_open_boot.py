"""Verify first native DI OPEN, source return and retained complete SC on fresh executions."""
from pathlib import Path
import base64
import hashlib
import json
import os
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'mass-di-open-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
base_path = root / 'mass-sysconf-complete-boot/build.json'
base = json.loads(base_path.read_text())
assert build['builderSha256'] == sha(experiment / 'build_di_open_boot.py')
assert build['baseBuildSha256'] == sha(base_path)
assert build['vendorDiSha256'] == sha(Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime/src/hle/devices/di_device.cpp'))
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
assert len(build['records']) == 125
assert [row['file'] for row, old in zip(build['records'], base['records']) if row != old] == ['output_62.cpp', 'output_65.cpp', 'output_67.cpp']
for row, old in zip(build['records'], base['records']):
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    current, previous = Path(row['source']).read_text(), Path(old['source']).read_text()
    if row['file'] == 'output_65.cpp':
        addition = '\n    nwii::runtime::experiment_di_return_observe(ctx);'
        assert current.count(addition) == 1 and current.replace(addition, '') == previous
    else:
        assert current == previous
for name in ('stm_device.cpp', 'fs_device.cpp', 'es_device.cpp'):
    assert sha(output / name) == sha(base_path.parent / name)
oracle_path = root / 'dolphin-di-events-disc/fpr-init-true-dolphin.json'
oracle = json.loads(oracle_path.read_text(encoding='utf-8-sig'))
di_raw = base64.b64decode(oracle['events'])
di_return = di_raw[64 + 76 * 1280:64 + 77 * 1280]
sc_oracle = json.loads((root / 'dolphin-sysconf-events-fixed-disc/fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
raw = base64.b64decode(sc_oracle['events'])
events = [raw[64 + i * 1280:64 + (i + 1) * 1280] for i in range(115)]
product_oracle = json.loads((root / 'dolphin-sysconf-product-oracle-disc/fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
data = base64.b64decode(product_oracle['data'])[15 * 736:16 * 736]
conf, product = (base64.b64decode(product_oracle[key]) for key in ('confPhysical', 'productPhysical'))
cache = json.loads((root / 'dolphin-sysconf-cache-oracle-disc/fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
parsed = base64.b64decode(cache['parsedCache'])
sc_parent = experiment / 'audit_sysconf_complete_boot.py'
function = sc_parent.read_text().split('\ndef check(lines, enabled):', 1)[1].split('\n\nexe =', 1)[0]
function = function[:function.index("    packet = bytes(map(int, one('SC_COMPLETE_NEXT_PACKET')))")]
function = function.replace("assert 'BOOT_STM submitted=28 produced=13' in lines", "assert ('BOOT_STM submitted=30 produced=14' if any(line.startswith('DI_ORIGINAL_RETURN ') for line in lines) else 'BOOT_STM submitted=28 produced=13') in lines")
function = function.replace("assert 'BOOT_SI_DELIVERY entries=31 callbacks=4' in lines", "assert ('BOOT_SI_DELIVERY entries=33 callbacks=4' if any(line.startswith('DI_ORIGINAL_RETURN ') for line in lines) else 'BOOT_SI_DELIVERY entries=31 callbacks=4') in lines")
exec(compile('def check_sc(lines, enabled):' + function, str(sc_parent), 'exec'), globals())


def check(lines, enabled):
    check_sc(lines, True)
    returns = [line for line in lines if line.startswith('DI_ORIGINAL_RETURN ')]
    if not enabled:
        assert not returns and 'BOOT_STM submitted=28 produced=13' in lines
        return
    assert returns == ['DI_ORIGINAL_RETURN 1 a032 3 935e25c0 935e2540 935e25e0 935e0060 50 f f']
    expected = bytearray(di_return[64:128])
    assert struct.unpack_from('>I', expected, 24)[0] == 0x8053ff90
    struct.pack_into('>I', expected, 24, 0x80540010)
    for view in ('CACHED', 'PHYSICAL'):
        rows = [line.split()[1:] for line in lines if line.startswith('DI_REPLY_' + view + ' ')]
        assert len(rows) == 1 and bytes(map(int, rows[0])) == expected
    assert 'BOOT_STM submitted=30 produced=14' in lines
    assert 'BOOT_SI_DELIVERY entries=33 callbacks=4' in lines
    packet_line = next(line for line in lines if line.startswith('BOOT_STM_NEXT_PACKET '))
    values = list(map(int, packet_line.split()[1:]))
    assert values[0] == 0x135e0080
    assert struct.unpack('>8I', bytes(values[1:33])) == (6, 3, 3, 0x86, 0x135e2560, 32, 0, 0)
    assert bytes(values[33:]) == bytes(32)


exe = output / 'openshsm-mass-boot'
assert sha(exe) == build['executableSha256']
observations = {}
for mode in ('live', 'disabled'):
    env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
    env.update(SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin',
        SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF',
        SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')
    if mode == 'disabled':
        env['SHSM_DI_OPEN_DISABLED'] = '1'
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(output / 'boot-quarantine.tsv'),
        str(root / 'sram-native/settings.bin')], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 7 and not result.stderr
    (output / (mode + '-audit.log')).write_text(result.stdout)
    observations[mode] = result.stdout.splitlines()
    check(observations[mode], mode == 'live')
prefixes = ['DI_ORIGINAL_RETURN', 'DI_REPLY_CACHED', 'DI_REPLY_PHYSICAL', 'BOOT_STM_NEXT_PACKET',
    'SC_STATUS_ORIGINAL_RETURN', 'SC_COMPLETE_CONF_CACHED', 'SC_COMPLETE_PRODUCT_PHYSICAL', 'BOOT_STM_ASYNC dispatched=']
for prefix in prefixes:
    try:
        check([line for line in observations['live'] if not line.startswith(prefix)], True)
    except (AssertionError, StopIteration):
        pass
    else:
        raise AssertionError('Missing DI/SC/pending evidence accepted: ' + prefix)
(output / 'audit.json').write_text(json.dumps({'result': 'NATIVE_FIRST_DI_OPEN_SOURCE_RETURN_REPLY_HEAP_SC_PENDING_PASS',
    'verifierSha256': sha(Path(__file__)), 'buildSha256': sha(output / 'build.json'), 'oracleSha256': sha(oracle_path),
    'scVerifierSha256': sha(sc_parent), 'mutantsRejected': len(prefixes),
    'limits': ['Original SDK runs unchanged apart from read-only return observer; kernel allocates FD3, no forced descriptor.',
        'Native empty queue15 vs original16 follows disclosed initial-counter offset; PC ACK64/reply65 not physical timing.',
        'Next DI command86 is stopped BEFORE submission; no disc-read/first-screen evidence.']}, indent=2) + '\n')
print('PASS fresh native DI OPEN/SDKreturn1-FD3/reply64x2/heap0060/fullSC/STM/disabled;8mutants; next DI86 BEFORE send')

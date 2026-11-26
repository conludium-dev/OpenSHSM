"""Validate original callback ownership and cached/physical prepared SC state."""
from pathlib import Path
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'mass-sysconf-payload-observer'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = json.loads((output / 'observation.json').read_text())
base_path = root / 'mass-es-close-boot/build.json'
base = json.loads(base_path.read_text())
assert report['builderSha256'] == sha(experiment / 'observe_sysconf_payload.py')
assert report['parentObserverSha256'] == sha(experiment / 'observe_es_vector_boot.py')
assert report['baseBuildSha256'] == sha(base_path) and report['records'] == base['records']
for path, digest in {**report['sourceHashes'], **report['headerHashes']}.items():
    assert sha(Path(path)) == digest
for path in output.glob('*.h'):
    assert sha(path) == sha(base_path.parent / path.name)
for row in report['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
assert len(report['records']) == 125
assert report['executableSha256'] == sha(output / 'es-vector-observer')
log = output / 'observation.log'
assert report['logSha256'] == sha(log)
lines = log.read_text().splitlines()
work = bytearray(0x140)
work[:64] = b'/shared2/sys/SYSCONF'.ljust(64, b'\0')
struct.pack_into('>3I', work, 0x100, 0x80244e30, 0x804b3094, 0)
control = bytearray(0x190)
struct.pack_into('>2I', control, 0x98, 0x80247730, 0x804b3008)
struct.pack_into('>6I', control, 0x164, 0x803dd730, 0x803dd748, 0x804b31a0, 0x80003800, 0x4000, 0x100)
packet = struct.pack('>12I', 1, 0, 0, 0x1d, 1, 1, 0x80540010, 0, 0x80240680, 0x935e1020, 0, 0) + bytes(16)
old_reply = struct.pack('>8I', 8, 0, 2, 0x1d, 1, 1, 0x80540010, 0) + bytes(32)


def check(current):
    def data(prefix):
        rows = [line for line in current if line.startswith(prefix + ' ')]
        assert len(rows) == 1, prefix
        return bytes(map(int, rows[0].split()[1:]))

    assert 'SC_FLUSH_ARGUMENTS 8053ff80 935e1040 1 935e1020 80240680 935e0080' in current
    assert data('SC_WORK_CACHED') == work
    assert data('SC_WORK_PHYSICAL') == work[:32] + bytes(0x140 - 32)
    assert data('SC_CONTROL_CACHED') == control and data('SC_CONTROL_PHYSICAL') == bytes(0x190)
    assert data('SC_PACKET_CACHED') == packet and data('SC_PACKET_PHYSICAL') == old_reply
    assert data('SC_CONF_HEAD_CACHED') == b'SCv0' + bytes(3) + b'\x08' + bytes(24)
    assert data('SC_CONF_TAIL_CACHED') == bytes(4) + b'SCed'
    assert data('SC_CONF_HEAD_PHYSICAL') == bytes(32) and data('SC_CONF_TAIL_PHYSICAL') == bytes(8)
    assert 'SC_FLAGS 1 1 1' in current
    assert 'SC_BOOT_PROFILE 80000000 0' in current
    assert 'BOOT_STM submitted=16 produced=7' in current
    assert 'BOOT_STM_ASYNC dispatched=1 pending=1 6 1 324927520 4096 4796512 32 4796544 32' in current
    assert any(line.startswith('BOOT_BOUNDARY pc=80212ff4 lr=8024250c msr=a032') for line in current)


check(lines)
mutants = 0
for prefix, index in [('SC_WORK_CACHED', 257), ('SC_WORK_CACHED', 261), ('SC_WORK_PHYSICAL', 257),
    ('SC_CONTROL_CACHED', 153), ('SC_CONTROL_CACHED', 157), ('SC_CONTROL_CACHED', 373),
    ('SC_CONTROL_PHYSICAL', 153), ('SC_PACKET_CACHED', 33), ('SC_PACKET_PHYSICAL', 1),
    ('SC_CONF_HEAD_CACHED', 1), ('SC_CONF_TAIL_CACHED', 5), ('SC_CONF_HEAD_PHYSICAL', 1)]:
    changed = list(lines)
    slot = next(i for i, line in enumerate(changed) if line.startswith(prefix + ' '))
    parts = changed[slot].split()
    parts[index] = str(int(parts[index]) ^ 1)
    changed[slot] = ' '.join(parts)
    try:
        check(changed)
    except AssertionError:
        mutants += 1
assert mutants == 12
proof_path = root / 'sysconf-source/ghidra/verification.json'
proof = json.loads(proof_path.read_text())
assert proof['runnerSha256'] == sha(experiment / 'verify_sysconf_ghidra.py')
assert len(proof['records']) == 8 and sum(row['instructions'] for row in proof['records']) == 462
assert sum(row['bytes'] for row in proof['records']) == 1848
for row in proof['records']:
    assert row['discoveredBodyBytes'] == (280 if row['name'] == 'IOS_OpenAsync' else row['bytes'])
    for suffix, key in (('asm', 'assemblySha256'), ('c', 'decompiledSha256')):
        assert sha(proof_path.parent / (row['name'] + '.' + suffix)) == row[key]
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
layout = struct.unpack('>64I', original[:256])
opcodes = [(0x802417cc, 0x93830100), (0x802417dc, 0x93a30104), (0x802417e0, 0x90030108),
    (0x802417fc, 0x48000c35), (0x802407b4, 0x819f0100), (0x802407c4, 0x809f0104),
    (0x802407cc, 0x4e800421), (0x802407e0, 0x480030d1), (0x80244e58, 0x90650000),
    (0x80247780, 0x4bffcb71), (0x80247828, 0x80040174), (0x8024782c, 0x7c030040),
    (0x802476bc, 0x388da5b0), (0x802476cc, 0xb01d0006),
    (0x80210a4c, 0x8003002c), (0x80210a58, 0x3c601000), (0x80210a5c, 0x38630002),
    (0x802424d8, 0x4800000c), (0x802424dc, 0x60000000)]
for address, opcode in opcodes:
    section = next(i for i in range(7) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
    assert struct.unpack_from('>I', original, layout[section] + address - layout[18 + section])[0] == opcode
(output / 'verification.json').write_text(json.dumps({'result': 'PREPARED_SYSCONF_CACHED_CALLBACK_CHAIN_EMPTY_SDK_BUFFER_BOOT_PROFILE_PASS',
    'verifierSha256': sha(Path(__file__)), 'observationSha256': sha(output / 'observation.json'), 'ghidraSha256': sha(proof_path),
    'rejectedObservationMutants': mutants, 'checkedDolOpcodes': len(opcodes),
    'limits': ['No OPEN submission or completed read/callback. Empty SCv0/SCed buffer is SDK preparation, not read file content.',
        'IsDevKit1 is observed because BootInfo+2C is zero and original OSGetConsoleType falls back; retail boot profile requires separate validation.',
        'Original callback invokes higher layers before freeing work; exact timing/reentrant allocation/IOS file response still unverified.']}, indent=2) + '\n')
print('PASS cached callback3layers/physical stale metadata/empty SCv0-SCed/boot profile;125 objects unchanged;19DOLwords/Ghidra462-1848/12mutants')

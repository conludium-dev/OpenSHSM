"""Verify read-only boot observation and compare installed vector against the owned DOL."""
from pathlib import Path
import hashlib
import json
import re
import struct

root = Path('work/private-game/static-recomp')
output = root / 'mass-interrupt-enable-observer'
base = root / 'mass-finite-mem2-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert build['builderSha256'] == sha(Path('experiments/wii-static-recomp/observe_interrupt_enable_boot.py'))
assert build['baseBootSha256'] == sha(base / 'boot.json')
assert build['records'] == json.loads((base / 'boot.json').read_text())['records']
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for path, digest in build['sourceHashes'].items():
    assert sha(Path(path)) == digest
assert build['executableSha256'] == sha(output / 'openshsm-mass-boot')
for filename in ('mass_boot.cpp', 'boot-quarantine.tsv', 'memory_protection_frontend.h', 'finite_mem2_clear.h'):
    assert (output / filename).read_bytes() == (base / filename).read_bytes()
wrapper = (output / 'boot-wrapper.cpp').read_text()
seam = '        experiment_interrupt_enable_observe(context);\n'
assert wrapper.count(seam) == 1 and wrapper.replace(seam, '') == (base / 'boot-wrapper.cpp').read_text()
log_path = output / 'observed-boot.log'
assert build['logSha256'] == sha(log_path)
log = log_path.read_text()
def fields(tag):
    lines = [line for line in log.splitlines() if line.startswith(tag + ' ')]
    assert len(lines) == 1
    return [int(value, 16) for value in lines[0].split()[1:]]
state = fields('IRQ_ENABLE_STATE')
assert state == [0x8021750c, 0x80211630, 0xa032, 8, 0xf8, 8, 0xe0010300, 0xc0010301, 1, 0]
os_pairs = fields('IRQ_ENABLE_OS')
os_state = dict(zip(os_pairs[::2], os_pairs[1::2]))
assert os_state == {0x800000c0: 0x492658, 0x800000d4: 0x80492658, 0x80003010: 0x80217c60,
    0x8052aad8: 0x80003040, 0x80003090: 0x8020f850, 0x800000c4: 0xf7fff7f0,
    0x800000c8: 0, 0x8052ab00: 0, 0x8052ab04: 0}
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = struct.unpack('>64I', dol[:256])
slot = next(i for i in range(7) if header[18 + i] <= 0x80211ba0 and header[18 + i] + header[36 + i] >= 0x80211c38)
vector = list(struct.unpack_from('>38I', dol, header[slot] + 0x80211ba0 - header[18 + slot]))
assert vector[26] == 0x38600000
vector[26] = 0x38600004
assert fields('IRQ_ENABLE_VECTOR') == vector
boundary = next(line for line in log.splitlines() if line.startswith('BOOT_BOUNDARY '))
assert re.fullmatch(r'BOOT_BOUNDARY pc=8021750c lr=80211630 msr=a032 calls=\d+ reason=SI external delivery producer/mask unverified', boundary)
assert 'BOOT_FINITE_MEM2 steps=1765312 returned=1' in log
(output / 'audit.json').write_text(json.dumps({'result': 'BOOT_PENDING_SI8_MASKF8_ORIGINAL_CONTEXT_VECTOR_CONFIRMED',
    'buildSha256': sha(output / 'build.json'), 'auditorSha256': sha(Path(__file__)),
    'state': state, 'osState': {f'{key:08x}': f'{value:08x}' for key, value in os_state.items()},
    'inferredBehavior': 'Old isolated mask8/context80501000 delivery profile excludes actual startup state.',
    'limits': ['No delivery enabled, pending bits cleared or OS context overwritten.',
        'Observer cached reads may allocate lines; original delivery behavior still needs separate oracle.']}, indent=2) + '\n')
print('PASS exact SI pending8/maskF8/context80492658/vector38 observation; original refusal retained')

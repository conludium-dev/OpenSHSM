"""Identify the owned Wii OSInit MEM2 producer and missing experimental loader fields."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess

root = Path('work/private-game/static-recomp')
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
dol = dol_path.read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
sections = []
for index in range(18):
    offset = struct.unpack_from('>I', dol, index * 4)[0]
    address = struct.unpack_from('>I', dol, 0x48 + index * 4)[0]
    size = struct.unpack_from('>I', dol, 0x90 + index * 4)[0]
    if size:
        sections.append((address, size, offset))

def word(address, default=None):
    for base, size, offset in sections:
        if base <= address and address + 4 <= base + size:
            return struct.unpack_from('>I', dol, offset + address - base)[0]
    assert default is not None, hex(address)
    return default

expected = {
    0x80211504: 0x80633124,
    0x8021150c: 0x4182006c,
    0x80211574: 0x480014ed,
    0x8021157c: 0x80633128,
    0x80211584: 0x41820008,
    0x80211588: 0x480014a9,
    0x80212a60: 0x906da2e4,
    0x80528a04: 0xffffffff,
}
for address, value in expected.items():
    assert word(address) == value, hex(address)
entry = root / 'mass-dc-zero-boot/mass_boot.cpp'
source = entry.read_text()
start = source.index('if (!std::getenv("SHSM_MI_NO_SIZE_FIXTURE"))')
seed = source[start:source.index('context.gpr.fill(0);', start)]
assert '0x3124' not in seed and '0x3128' not in seed
assert word(0x80003124, 0) == word(0x80003128, 0) == 0
assert 'context.mmu.write32(seed[0], seed[1]);' in seed
result = subprocess.run(['python3', 'experiments/wii-static-recomp/audit_dc_zero_boot.py'],
    capture_output=True, text=True, timeout=60)
assert result.returncode == 0, result.stdout + result.stderr
report = {
    'result': 'OWNED_DOL_MEM2_PRODUCER_DEPENDS_ON_UNPREPARED_LOADER_FIELDS',
    'dolSha256': hashlib.sha256(dol).hexdigest(),
    'entrySha256': hashlib.sha256(entry.read_bytes()).hexdigest(),
    'auditorSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'originalBehavior': 'OSInit reads 80003124/80003128; zero skips respective setters. Initial MEM2 arena low is FFFFFFFF.',
    'pcAdaptation': 'Current experimental loader prepares memory sizes, but not these two arena fields.',
    'inferredBehavior': 'Missing loader fields explain why the initial low sentinel survives to ClearMEM2Arena.',
    'instructionWords': {f'{address:08x}': f'{value:08x}' for address, value in expected.items()},
    'bootAuditSha256': hashlib.sha256((root / 'mass-dc-zero-boot/audit.json').read_bytes()).hexdigest(),
    'limits': [
        'No original-loader values inferred from memory sizes or directly written to SDK arena variables.',
        'Original boot low-memory snapshot and native instruction trace still required before fixing loader.',
        'No first screen/menu/audio or completed phone/IntroTown/controller claim.',
    ],
}
output = root / 'mem2-loader-analysis'
output.mkdir(exist_ok=True)
(output / 'analysis.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS owned DOL MEM2 producer: absent loader 3124/3128; original low sentinel FFFFFFFF; boot refusal retained')

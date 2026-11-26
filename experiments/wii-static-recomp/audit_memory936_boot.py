"""Verify scoped source merge and retained finite-clear polling boundary."""
from pathlib import Path
import hashlib
import json
import re

root = Path('work/private-game/static-recomp')
output = root / 'mass-memory936-boot'
base = root / 'mass-mem2-loader-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'boot.json').read_text())
assert build['builderSha256'] == sha(Path('experiments/wii-static-recomp/build_memory936_boot.py'))
assert build['baseBootSha256'] == sha(base / 'boot.json')
assert build['profileProofSha256'] == sha(root / 'memory936-native/comparison.json')
assert build['donorSha256'] == sha(root / 'memory936-native/output_63.cpp')
assert build['executableSha256'] == sha(output / 'openshsm-mass-boot')
before_build = json.loads((base / 'boot.json').read_text())
for row, prior in zip(build['records'], before_build['records']):
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    if row['file'] != 'output_63.cpp':
        assert row == prior
    else:
        start, end = 'void func_802181D0(CPUContext& ctx) {', 'void func_802182B0(CPUContext& ctx) {'
        original = Path(prior['source']).read_text()
        merged = Path(row['source']).read_text()
        donor = (root / 'memory936-native/output_63.cpp').read_text()
        old = original[original.index(start):original.index(end)]
        new = donor[donor.index(start):donor.index(end)]
        assert merged == original.replace(old, new, 1)
assert (output / 'mass_boot.cpp').read_bytes() == (base / 'mass_boot.cpp').read_bytes()
assert (output / 'boot-quarantine.tsv').read_text() == (base / 'boot-quarantine.tsv').read_text().replace(build['removedPolicy'], '')
for path, digest in build['sourceHashes'].items():
    assert sha(Path(path)) == digest
for filename in ('memory_protection_frontend.h', 'memory-protection-bat-plan.h'):
    assert (output / filename).read_bytes() == (root / 'memory936-native' / filename).read_bytes()
for filename in ('dc_zero_frontend.h', 'reset_code_frontend.h'):
    assert (output / filename).read_bytes() == (Path('experiments/wii-static-recomp') / filename).read_bytes()
log = (output / 'live-boot.log').read_text()
assert build['results']['live']['returnCode'] == 7 and build['results']['live']['logSha256'] == sha(output / 'live-boot.log')
boundary = next(line for line in log.splitlines() if line.startswith('BOOT_BOUNDARY '))
assert re.fullmatch(r'BOOT_BOUNDARY pc=80213084 lr=80210ec8 msr=2032 calls=\d+ reason=Pre-service polling budget exceeded', boundary)
assert 'BOOT_MI phase=3 writes=3 realEntries=2 active=0 mask=16' in log
assert 'BOOT_DSP commands=17 completed=2 accesses=24' in log
assert 'BOOT_FLUSH entries=2 phase=0 barriers=2' in log and 'BOOT_DCZERO lines=958014' in log
registers = list(map(int, next(line for line in log.splitlines() if line.startswith('BOOT_REGISTERS ')).split()[1:]))
assert 0x90000800 < registers[3] < 0x935e0000 and registers[4] == (0x935e0000 - 0x90000800) // 32
(output / 'audit.json').write_text(json.dumps({'result': 'SCOPED_MEMORY936_BOOT_PASSES_BAT_REACHES_MEM2_FINITE_CLEAR_BUDGET',
    'buildSha256': sha(output / 'boot.json'), 'auditorSha256': sha(Path(__file__)), 'boundary': boundary,
    'limits': ['Audits retained run, not a fresh replay; no first frame/menu/audio.',
        'Finite-clear budget handling and current-object regressions still pending.']}, indent=2) + '\n')
print('PASS one-body merge/124objects retained;936BAT returns; MEM2 address valid; finite-clear budget still enforced')

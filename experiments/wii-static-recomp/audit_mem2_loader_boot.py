"""Verify that measured loader fields are rejected by the previous 93400000-only profile."""
from pathlib import Path
import hashlib
import json
import re

root = Path('work/private-game/static-recomp')
output = root / 'mass-mem2-loader-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'boot.json').read_text())
assert build['builderSha256'] == sha(Path('experiments/wii-static-recomp/build_mem2_loader_boot.py'))
assert build['loaderProofSha256'] == sha(root / 'dolphin-loader-snapshot/comparison.json')
assert build['entryBeforeSha256'] == sha(root / 'mass-dc-zero-boot/mass_boot.cpp')
assert build['entryAfterSha256'] == sha(output / 'mass_boot.cpp')
assert build['executableSha256'] == sha(output / 'openshsm-mass-boot')
assert (output / 'boot-quarantine.tsv').read_bytes() == (root / 'mass-dc-zero-boot/boot-quarantine.tsv').read_bytes()
assert build['loaderFields']['00003120'] == '93600000'
for path, digest in build['sourceHashes'].items():
    assert sha(Path(path)) == digest
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for mode in ('live', 'disabled'):
    path = output / (mode + '-boot.log')
    assert sha(path) == build['results'][mode]['logSha256']
    assert build['results'][mode]['returnCode'] == 7
    log = path.read_text()
    boundary = next(line for line in log.splitlines() if line.startswith('BOOT_BOUNDARY '))
    assert re.fullmatch(r'BOOT_BOUNDARY pc=802184f0 lr=80218578 msr=2032 calls=\d+ reason=Memory-protection size profile unverified', boundary)
    assert 'BOOT_MI phase=2 writes=2 realEntries=0 active=0 mask=0' in log
    assert 'BOOT_DSP commands=17 completed=2 accesses=24' in log
(output / 'audit.json').write_text(json.dumps({
    'result': 'MEASURED_LOADER936_PROFILE_REJECTED_PRIOR934_ONLY_GUARD',
    'buildSha256': sha(output / 'boot.json'), 'auditorSha256': sha(Path(__file__)),
    'limits': ['Candidate does not advance boot; previous accepted DCZero boot retained separately.',
        'Disabled candidate also omits size fields; not an exact earlier-boot replay.',
        'Next original whole memory-protection comparison for measured936profile before extending guard.'],
}, indent=2) + '\n')
print('PASS measured loader candidate retained size guard; original/reference936memory-protection verification pending')

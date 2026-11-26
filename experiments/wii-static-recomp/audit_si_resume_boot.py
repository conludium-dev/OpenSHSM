"""Verify one dispatcher continuation and fresh boot progress beyond all four SI interrupts."""
from pathlib import Path
import hashlib
import json
import os
import re
import struct
import subprocess

root = Path('work/private-game/static-recomp')
output = root / 'mass-si-resume-boot'
base = root / 'mass-finite-mem2-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert build['builderSha256'] == sha(Path('experiments/wii-static-recomp/build_si_resume_boot.py'))
assert build['parentBuilderSha256'] == sha(Path('experiments/wii-static-recomp/build_si_queue_boot.py'))
assert build['queueProofSha256'] == sha(root / 'si-queue-native/comparison.json')
prior = json.loads((base / 'boot.json').read_text())
added = '            case 0x8021750C: func_80217500(ctx); break;\n'
for row, old in zip(build['records'], prior['records']):
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    if row['file'] != 'main_output.cpp':
        assert row == old
    else:
        text = Path(row['source']).read_text()
        assert text.count(added) == 1 and text.replace(added, '') == Path(old['source']).read_text()
        assert '{0x801B55B0, 0x80224130, func_801B55B0}' in text
body_row = next(row for row in build['records'] if row['file'] == 'output_63.cpp')
assert 'case 0x8021750C: goto loc_8021750C;' in Path(body_row['source']).read_text()
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
layout = struct.unpack('>64I', dol[:256])
slot = next(index for index in range(7) if layout[18 + index] <= 0x8021750c < layout[18 + index] + layout[36 + index])
assert struct.unpack_from('>I', dol, layout[slot] + 0x8021750c - layout[18 + slot])[0] == 0x54638ffe
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
for filename in ('mass_boot.cpp', 'boot-quarantine.tsv'):
    assert (output / filename).read_bytes() == (base / filename).read_bytes()
assert build['executableSha256'] == sha(output / 'openshsm-mass-boot')
def validate(log):
    assert 'BOOT_SI_DELIVERY entries=4 callbacks=4' in log
    assert 'BOOT_FINITE_MEM2 steps=1765312 returned=1' in log
    assert 'BOOT_FLUSH entries=3 phase=0 barriers=3' in log
    assert 'BOOT_MI phase=3 writes=3 realEntries=2 active=0 mask=16' in log
    assert 'BOOT_DSP commands=17 completed=2 accesses=24' in log
    boundary = next(line for line in log.splitlines() if line.startswith('BOOT_BOUNDARY '))
    assert re.fullmatch(r'BOOT_BOUNDARY pc=80241c30 lr=80242140 msr=a032 calls=\d+ reason=BAT MMIO/locked-cache/unmapped backing access unavailable', boundary)
    assert [line for line in log.splitlines() if line.startswith('BOOT_TRACE ')][-1] == 'BOOT_TRACE address=80241c30'
    return boundary
assert build['logSha256'] == sha(output / 'observed-boot.log')
validate((output / 'observed-boot.log').read_text())
environment = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
fresh = subprocess.run([str(output / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol',
    str(output / 'boot-quarantine.tsv'), str(root / 'sram-native/settings.bin')], env=environment,
    capture_output=True, text=True, timeout=30)
assert fresh.returncode == 7 and not fresh.stderr
boundary = validate(fresh.stdout)
diagnostic = root / 'mass-si-queue-fallback-observer/observed-boot.log'
assert 'func_801B55B0' in diagnostic.read_text()
(output / 'audit.json').write_text(json.dumps({'result': 'FOUR_SI_IRQS_RETURN_EXISTING_DISPATCH_RESUME_VERIFIED_NEXT_IPC_BOUNDARY',
    'buildSha256': sha(output / 'build.json'), 'auditorSha256': sha(Path(__file__)), 'freshBoundary': boundary,
    'fallbackStackSha256': sha(diagnostic),
    'limits': ['One owned-DOL-verified continuation alias; other overlapping bounds remain unresolved.',
        'Next exact faulting IPC access not yet observed; no blanket MMIO/interpretation permission.',
        'No original screen/menu/audio/controller/full-game acceptance.']}, indent=2) + '\n')
print('PASS fresh four SI IRQ/callback returns + exact dispatcher alias; next guarded IPC boundary80241C30')

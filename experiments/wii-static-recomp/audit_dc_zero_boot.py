"""Verify first arena zeroing returns and invalid MEM2 arena input remains refused."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
private = Path('work/private-game/static-recomp')
experiment = Path('experiments/wii-static-recomp')
output = private / 'mass-dc-zero-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'boot.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_dc_zero_boot.py')
assert build['nativeBuildSha256'] == sha(private / 'dc-zero-native/build.json')
assert build['nativeProofSha256'] == sha(private / 'dc-zero-native/comparison.json')
assert build['entryBeforeSha256'] == sha(private / 'mass-reset-code-boot/mass_boot.cpp')
assert build['entryAfterSha256'] == sha(output / 'mass_boot.cpp')
assert build['executableSha256'] == sha(output / 'openshsm-mass-boot')
policy = (private / 'mass-reset-code-boot/boot-quarantine.tsv').read_text()
assert policy.count(build['removedPolicy']) == 1
assert (output / 'boot-quarantine.tsv').read_text() == policy.replace(build['removedPolicy'], '')
assert build['policySha256'] == sha(output / 'boot-quarantine.tsv')
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for path, digest in build['sourceHashes'].items():
    assert sha(Path(path)) == digest
def validate(mode, text):
    boundary = [line for line in text.splitlines() if line.startswith('BOOT_BOUNDARY ')]
    assert len(boundary) == 1
    assert 'BOOT_DSP commands=17 completed=2 accesses=24' in text
    assert 'BOOT_MI phase=3 writes=3 realEntries=2 active=0 mask=16' in text
    assert 'BOOT_PC_CLOCK phase=6 writes=6' in text
    if mode == 'live':
        assert re.fullmatch(r'BOOT_BOUNDARY pc=80213060 lr=80210ec8 msr=2032 calls=\d+ reason=No verified BAT mapping; page-table/exception path unavailable', boundary[0])
        assert 'BOOT_DCZERO lines=581370' in text and 'BOOT_FLUSH entries=2 phase=0 barriers=2' in text
        registers = [int(value) for value in next(line for line in text.splitlines() if line.startswith('BOOT_REGISTERS ')).split()[1:]]
        assert registers[3] == 0xffffffff and registers[4] == 1 and registers[5] == 31
    else:
        assert re.fullmatch(r'BOOT_BOUNDARY pc=80213060 lr=80210ce8 msr=2032 calls=\d+ reason=DCZeroRange cached dcbz profile unverified', boundary[0])
        assert 'BOOT_DCZERO lines=0' in text and 'BOOT_FLUSH entries=1 phase=0 barriers=1' in text
    return boundary[0]
fresh = {}
for mode in ('live', 'disabled'):
    saved = output / (mode + '-boot.log')
    assert build['results'][mode]['logSha256'] == sha(saved)
    validate(mode, saved.read_text())
    environment = dict(os.environ)
    for flag in ('SHSM_DC_ZERO_DISABLED', 'SHSM_RESET_DISABLED', 'SHSM_RI_UART_DISABLED', 'SHSM_FPU_DISABLED', 'SHSM_FLUSH_DISABLED',
            'SHSM_AI_CLOCK_NO_BUS', 'SHSM_SI_IDLE_REPLAY', 'SHSM_DSP_DISABLED', 'SHSM_DSP_LOST_DMA', 'SHSM_DSP_LOST_MAIL', 'SHSM_MI_DISABLED', 'SHSM_MI_NO_SIZE_FIXTURE'):
        environment.pop(flag, None)
    if mode == 'disabled':
        environment['SHSM_DC_ZERO_DISABLED'] = '1'
    result = subprocess.run([str(output / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol',
        str(output / 'boot-quarantine.tsv'), str(private / 'sram-native/settings.bin')], env=environment,
        capture_output=True, text=True, timeout=30)
    assert result.returncode == build['results'][mode]['returnCode'] == 7 and not result.stderr
    fresh[mode] = validate(mode, result.stdout)
(output / 'audit.json').write_text(json.dumps({'result': 'BOOT_MEM1_DCZERO_RETURNS_INVALID_MEM2_ARENA_RETAINED',
    'buildSha256': sha(output / 'boot.json'), 'auditorSha256': sha(Path(__file__)), 'boundaries': fresh,
    'limits': ['581370lines is a deterministic private MEM1 fixture, not physical cache timing or completion percentage.',
        'Second caller ClearMEM2Arena passes FFFFFFFF; initialization/loader reason still needs original-source/oracle comparison.',
        'No original first frame/menu/audio/full-game acceptance.']}, indent=2) + '\n')
print('PASS first arena DCZeroRange returns/flush retained; invalid MEM2 FFFFFFFF refused; disabled zeroes no lines')

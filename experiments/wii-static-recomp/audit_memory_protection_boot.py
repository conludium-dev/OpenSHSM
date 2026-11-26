"""Verify original memory initialization returns and retains the next EXI refusal."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess

private = Path('work/private-game/static-recomp')
experiment = Path('experiments/wii-static-recomp')
output = private / 'mass-memory-protection-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'boot.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_memory_protection_boot.py')
assert build['nativeBuildSha256'] == sha(private / 'memory-protection-native/build.json')
assert build['nativeProofSha256'] == sha(private / 'memory-protection-native/comparison.json')
assert build['baseBootSha256'] == sha(private / 'mass-audio-init-boot/boot.json')
assert build['entryBeforeSha256'] == sha(private / 'mass-audio-init-boot/mass_boot.cpp')
assert build['entryAfterSha256'] == sha(output / 'mass_boot.cpp')
assert build['executableSha256'] == sha(output / 'openshsm-mass-boot')
assert build['planSha256'] == sha(output / 'memory-protection-bat-plan.h') == sha(private / 'memory-protection-native/memory-protection-bat-plan.h')
policy = (private / 'mass-audio-init-boot/boot-quarantine.tsv').read_text()
assert build['removedPolicy'] == ['80218070\t//_unhandled\n', '802180F0\t//_unhandled\n']
for line in build['removedPolicy']:
    assert policy.count(line) == 1
    policy = policy.replace(line, '')
assert (output / 'boot-quarantine.tsv').read_text() == policy and build['policySha256'] == sha(output / 'boot-quarantine.tsv')
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for name, digest in build['sourceHashes'].items():
    assert sha(Path(name)) == digest
reference = json.loads((private / 'dolphin-audio-trace/comparison.json').read_text())
expected_dsp = [[row['site'], row['value'], row['address']] for row in reference['traces'][0]]
def validate(mode, text):
    boundaries = [line for line in text.splitlines() if line.startswith('BOOT_BOUNDARY ')]
    assert len(boundaries) == 1
    boundary = boundaries[0]
    assert 'BOOT_FLUSH entries=1 phase=0 barriers=1' in text
    assert 'BOOT_PC_CLOCK phase=6 writes=6' in text
    assert 'BOOT_DSP commands=17 completed=2 accesses=24' in text
    dsp = [[int(value) for value in line.split()[1:]] for line in text.splitlines() if line.startswith('BOOT_DSP_ACCESS ')]
    assert [row[:3] for row in dsp] == expected_dsp and dsp[9][3] - dsp[8][3] >= 2194
    if mode == 'live':
        assert re.fullmatch(r'BOOT_BOUNDARY pc=8020e344 lr=8020e344 msr=2032 calls=\d+ reason=GetID MMIO profile mapping unverified', boundary)
        assert 'BOOT_MI phase=3 writes=3 realEntries=2 active=0 mask=16' in text
        assert 'BOOT_TRACE address=80218070' in text and 'BOOT_TRACE address=802180f0' in text
        assert 'BOOT_TRACE address=8020e310' in text
    elif mode == 'disabled':
        assert re.fullmatch(r'BOOT_BOUNDARY pc=802186a4 lr=802186a4 msr=2032 calls=\d+ reason=MI memory-protection command/profile unverified', boundary)
        assert 'BOOT_MI phase=0 writes=0 realEntries=0 active=0 mask=0' in text
    else:
        assert re.fullmatch(r'BOOT_BOUNDARY pc=802184f0 lr=80218578 msr=2032 calls=\d+ reason=Memory-protection size profile unverified', boundary)
        assert 'BOOT_MI phase=2 writes=2 realEntries=0 active=0 mask=0' in text
    return boundary
fresh = {}
for mode, flag in [('live', None), ('disabled', 'SHSM_MI_DISABLED'), ('no-size', 'SHSM_MI_NO_SIZE_FIXTURE')]:
    saved = output / (mode + '-boot.log')
    assert build['results'][mode]['logSha256'] == sha(saved)
    validate(mode, saved.read_text())
    environment = dict(os.environ)
    for name in ('SHSM_FPU_DISABLED', 'SHSM_FLUSH_DISABLED', 'SHSM_AI_CLOCK_NO_BUS', 'SHSM_SI_IDLE_REPLAY',
            'SHSM_DSP_DISABLED', 'SHSM_DSP_LOST_DMA', 'SHSM_DSP_LOST_MAIL', 'SHSM_MI_DISABLED', 'SHSM_MI_NO_SIZE_FIXTURE'):
        environment.pop(name, None)
    if flag:
        environment[flag] = '1'
    result = subprocess.run([str(output / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol',
        str(output / 'boot-quarantine.tsv'), str(private / 'sram-native/settings.bin')],
        env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == build['results'][mode]['returnCode'] == 7 and not result.stderr
    fresh[mode] = validate(mode, result.stdout)
(output / 'audit.json').write_text(json.dumps({'result': 'BOOT_MEMORY_PROTECTION_RETURNS_NEXT_EXI_RI_PROFILE_GUARD_RETAINED',
    'buildSha256': sha(output / 'boot.json'), 'auditorSha256': sha(Path(__file__)), 'freshBoundaries': fresh,
    'limits': ['Private loader size fixture disclosed; native call counts vary and are not acceptance criteria.',
        'Next PC8020E344 is preceding call return in EXISelect, not yet an exact MMIO access observation.',
        'No original screen/menu/audio/physical protection or full controller/game acceptance.']}, indent=2) + '\n')
print('PASS boot returns from memory protection; disabled/no-size controls refuse; DSP/clock/flush retained; next EXI guard retained')

"""Check boot passes the original DSP procedure and retains the next guard."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

private = Path('work/private-game/static-recomp')
output = private / 'mass-audio-init-boot'
experiment = Path('experiments/wii-static-recomp')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'boot.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_audio_init_boot.py')
assert build['nativeBuildSha256'] == sha(private / 'audio-init-native/build.json')
assert build['nativeProofSha256'] == sha(private / 'audio-init-native/comparison.json')
assert build['entryBeforeSha256'] == sha(private / 'mass-flush-syscall-boot/mass_boot.cpp')
assert build['entryAfterSha256'] == sha(output / 'mass_boot.cpp')
assert build['executableSha256'] == sha(output / 'openshsm-mass-boot')
assert build['policySha256'] == sha(output / 'boot-quarantine.tsv') == sha(private / 'mass-flush-syscall-boot/boot-quarantine.tsv')
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for name, digest in build['sourceHashes'].items():
    assert sha(Path(name)) == digest
reference = json.loads((private / 'dolphin-audio-trace/comparison.json').read_text())
expected_accesses = [[row['site'], row['value'], row['address']] for row in reference['traces'][0]]
def validate(mode, text):
    boundaries = [line for line in text.splitlines() if line.startswith('BOOT_BOUNDARY ')]
    assert len(boundaries) == 1
    boundary = boundaries[0]
    assert 'BOOT_FLUSH entries=1 phase=0 barriers=1' in text
    assert 'BOOT_PC_CLOCK phase=6 writes=6' in text
    assert 'BOOT_TRACE address=80212ce0' in text
    if mode == 'live':
        assert boundary.startswith('BOOT_BOUNDARY pc=802186a4 lr=802186a4 msr=2032 ')
        assert boundary.endswith('reason=BAT MMIO/locked-cache/unmapped backing access unavailable')
        assert 'BOOT_TRACE address=80218680' in text
        assert 'BOOT_DSP commands=17 completed=2 accesses=24' in text
        accesses = [[int(value) for value in line.split()[1:]] for line in text.splitlines() if line.startswith('BOOT_DSP_ACCESS ')]
        assert [row[:3] for row in accesses] == expected_accesses
        ticks = [row[3] for row in accesses]
        assert ticks == sorted(ticks) and ticks[9] - ticks[8] >= 2194
    elif mode == 'disabled':
        assert boundary.startswith('BOOT_BOUNDARY pc=80212d38 lr=80212d38 msr=2032 ')
        assert 'BOOT_DSP commands=0 completed=0 accesses=0' in text
    else:
        pc, commands, completed, accesses = ('80212db0', 7, 0, 8) if mode == 'lost-dma' else ('80212e48', 14, 2, 18)
        assert boundary.startswith('BOOT_BOUNDARY pc=' + pc + ' ')
        assert boundary.endswith('reason=Pre-service polling budget exceeded')
        assert f'BOOT_DSP commands={commands} completed={completed} accesses={accesses}' in text
    return boundary
fresh = {}
for mode, flag in [('live', None), ('disabled', 'SHSM_DSP_DISABLED'), ('lost-dma', 'SHSM_DSP_LOST_DMA'), ('lost-mail', 'SHSM_DSP_LOST_MAIL')]:
    saved = output / (mode + '-boot.log')
    assert build['results'][mode]['logSha256'] == sha(saved)
    validate(mode, saved.read_text())
    environment = dict(os.environ)
    for name in ('SHSM_FPU_DISABLED', 'SHSM_FLUSH_DISABLED', 'SHSM_AI_CLOCK_NO_BUS', 'SHSM_SI_IDLE_REPLAY',
            'SHSM_DSP_DISABLED', 'SHSM_DSP_LOST_DMA', 'SHSM_DSP_LOST_MAIL'):
        environment.pop(name, None)
    if flag:
        environment[flag] = '1'
    result = subprocess.run([str(output / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol',
        str(output / 'boot-quarantine.tsv'), str(private / 'sram-native/settings.bin')],
        env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == build['results'][mode]['returnCode'] == 7 and result.stderr == ''
    fresh[mode] = validate(mode, result.stdout)
(output / 'audit.json').write_text(json.dumps({'result': 'BOOT_ORIGINAL_AUDIO_STARTUP_PASSES_NEXT_MEMORY_PROTECTION_GUARD_RETAINED',
    'buildSha256': sha(output / 'boot.json'), 'auditorSha256': sha(Path(__file__)), 'freshBoundaries': fresh,
    'referenceSha256': sha(private / 'dolphin-audio-trace/comparison.json'),
    'limits': ['Live trace timing/call count may vary; measured24access order/values and inter-DMA minimum checked.',
        'Next PC802186A4 is preceding call return in __OSInitMemoryProtection, not an exact failing memory instruction.',
        'No first frame/menu/audio playback/full-game or physical Wii acceptance.']}, indent=2) + '\n')
print('PASS boot returns from original audio startup/24DSP accesses; disabled/lostDMA/lostMail stop; next memory-protection guard retained')

"""Check reset-code startup passes while the unimplemented dcbz procedure stays guarded."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
private = Path('work/private-game/static-recomp')
experiment = Path('experiments/wii-static-recomp')
output = private / 'mass-reset-code-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'boot.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_reset_code_boot.py')
assert build['parentBuilderSha256'] == sha(experiment / 'build_uart_ri_boot.py')
assert build['nativeBuildSha256'] == sha(private / 'reset-code-native/build.json')
assert build['nativeProofSha256'] == sha(private / 'reset-code-native/comparison.json')
assert build['entryBeforeSha256'] == sha(private / 'mass-uart-ri-boot/mass_boot.cpp')
assert build['entryAfterSha256'] == sha(output / 'mass_boot.cpp')
assert build['policySha256'] == sha(output / 'boot-quarantine.tsv') == sha(private / 'mass-uart-ri-boot/boot-quarantine.tsv')
assert build['executableSha256'] == sha(output / 'openshsm-mass-boot')
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for path, digest in build['sourceHashes'].items():
    assert sha(Path(path)) == digest
observer = private / 'mass-reset-code-observer'
observation = json.loads((observer / 'observation.json').read_text())
assert observation['builderSha256'] == sha(experiment / 'observe_reset_code_boot.py')
assert observation['observerSha256'] == sha(experiment / 'reset_code_observer.h')
assert observation['logSha256'] == sha(observer / 'boot.log')
assert observation['diagnostic'] == 'RESET_CODE_REFUSAL instruction=80219504 address=cc003024 physical=c003024 msr=2032 lr=80210ca8 wimg=5 slot=1 width=4'
def validate(mode, text):
    boundary = [line for line in text.splitlines() if line.startswith('BOOT_BOUNDARY ')]
    assert len(boundary) == 1
    assert 'BOOT_DSP commands=17 completed=2 accesses=24' in text
    assert 'BOOT_MI phase=3 writes=3 realEntries=2 active=0 mask=16' in text
    assert 'BOOT_FLUSH entries=1 phase=0 barriers=1' in text and 'BOOT_PC_CLOCK phase=6 writes=6' in text
    if mode == 'live':
        assert re.fullmatch(r'BOOT_BOUNDARY pc=80213060 lr=80210ce8 msr=2032 calls=\d+ reason=//_dcbz_\(data_cache_block_zero\)_-_stub', boundary[0])
        assert 'BOOT_RESET reads=1' in text
    else:
        assert re.fullmatch(r'BOOT_BOUNDARY pc=802194e0 lr=80210ca8 msr=2032 calls=\d+ reason=Cold reset-code caller/mapping/profile unverified', boundary[0])
        assert 'BOOT_RESET reads=0' in text
    return boundary[0]
fresh = {}
for mode in ('live', 'disabled'):
    saved = output / (mode + '-boot.log')
    assert build['results'][mode]['logSha256'] == sha(saved)
    validate(mode, saved.read_text())
    environment = dict(os.environ)
    for flag in ('SHSM_RESET_DISABLED', 'SHSM_RI_UART_DISABLED', 'SHSM_FPU_DISABLED', 'SHSM_FLUSH_DISABLED', 'SHSM_AI_CLOCK_NO_BUS',
            'SHSM_SI_IDLE_REPLAY', 'SHSM_DSP_DISABLED', 'SHSM_DSP_LOST_DMA', 'SHSM_DSP_LOST_MAIL', 'SHSM_MI_DISABLED', 'SHSM_MI_NO_SIZE_FIXTURE'):
        environment.pop(flag, None)
    if mode == 'disabled':
        environment['SHSM_RESET_DISABLED'] = '1'
    result = subprocess.run([str(output / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol',
        str(output / 'boot-quarantine.tsv'), str(private / 'sram-native/settings.bin')], env=environment,
        capture_output=True, text=True, timeout=30)
    assert result.returncode == build['results'][mode]['returnCode'] == 7 and not result.stderr
    fresh[mode] = validate(mode, result.stdout)
(output / 'audit.json').write_text(json.dumps({'result': 'BOOT_RESET_CODE_PASSES_DC_ZERO_RANGE_STUB_GUARD_RETAINED',
    'buildSha256': sha(output / 'boot.json'), 'auditorSha256': sha(Path(__file__)), 'boundaries': fresh,
    'limits': ['Cold PI0 profile only; no reset-button/event/non-cold hardware emulation.',
        'Quarantine stops before DCZeroRange body; no dcbz execution or memory-zeroing acceptance yet.',
        'No original frame/menu/audio/full-game acceptance.']}, indent=2) + '\n')
print('PASS boot completes reset-code read; disabled restores old stop; DCZeroRange dcbz stub remains guarded')

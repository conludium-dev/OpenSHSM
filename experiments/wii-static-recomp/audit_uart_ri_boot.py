"""Verify RI UART boot progress and exact observer lineage without claiming a frame."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'mass-uart-ri-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'boot.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_uart_ri_boot.py')
assert build['nativeBuildSha256'] == sha(private / 'uart-ri-native/build.json')
assert build['nativeProofSha256'] == sha(private / 'uart-ri-native/comparison.json')
assert build['entryBeforeSha256'] == sha(private / 'mass-memory-protection-boot/mass_boot.cpp')
assert build['entryAfterSha256'] == sha(output / 'mass_boot.cpp')
assert build['policySha256'] == sha(output / 'boot-quarantine.tsv') == sha(private / 'mass-memory-protection-boot/boot-quarantine.tsv')
assert build['executableSha256'] == sha(output / 'openshsm-mass-boot')
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for name, digest in build['sourceHashes'].items():
    assert sha(Path(name)) == digest
observer_path = private / 'mass-exi-ri-observer'
observer = json.loads((observer_path / 'observation.json').read_text())
assert observer['builderSha256'] == sha(experiment / 'observe_exi_ri_boot.py')
assert observer['observerSha256'] == sha(experiment / 'exi_ri_observer.h')
assert observer['logSha256'] == sha(observer_path / 'boot.log')
assert observer['diagnostic'] == 'EXI_RI_REFUSAL instruction=8020e3c0 address=cd006800 physical=d006800 msr=2032 lr=8020e344 channel=0 device=1 clock=4 csr=1008 wimg=5 slot=1 width=4'
row = next(row for row in observer['records'] if row['file'] == 'output_62.cpp')
reconstructed = Path(row['source']).read_text()
for change in observer['changes']:
    assert reconstructed.count(change['after']) == 1
    reconstructed = reconstructed.replace(change['after'], change['before'])
assert reconstructed == Path(row['inputSource']).read_text()
reference = json.loads((private / 'dolphin-audio-trace/comparison.json').read_text())
expected_dsp = [[row['site'], row['value'], row['address']] for row in reference['traces'][0]]
def validate(mode, text):
    boundaries = [line for line in text.splitlines() if line.startswith('BOOT_BOUNDARY ')]
    assert len(boundaries) == 1
    boundary = boundaries[0]
    assert 'BOOT_MI phase=3 writes=3 realEntries=2 active=0 mask=16' in text
    assert 'BOOT_DSP commands=17 completed=2 accesses=24' in text
    assert 'BOOT_FLUSH entries=1 phase=0 barriers=1' in text
    assert 'BOOT_PC_CLOCK phase=6 writes=6' in text
    dsp = [[int(value) for value in line.split()[1:]] for line in text.splitlines() if line.startswith('BOOT_DSP_ACCESS ')]
    assert [row[:3] for row in dsp] == expected_dsp and dsp[9][3] - dsp[8][3] >= 2194
    if mode == 'live':
        assert re.fullmatch(r'BOOT_BOUNDARY pc=802194e0 lr=80210ca8 msr=2032 calls=\d+ reason=BAT MMIO/locked-cache/unmapped backing access unavailable', boundary)
        assert 'BOOT_TRACE address=802194e0' in text and 'BOOT_TRACE address=80210c90' in text
    else:
        assert re.fullmatch(r'BOOT_BOUNDARY pc=8020e344 lr=8020e344 msr=2032 calls=\d+ reason=GetID MMIO profile mapping unverified', boundary)
    return boundary
fresh = {}
for mode in ('live', 'disabled'):
    saved = output / (mode + '-boot.log')
    assert build['results'][mode]['logSha256'] == sha(saved)
    validate(mode, saved.read_text())
    environment = dict(os.environ)
    for flag in ('SHSM_RI_UART_DISABLED', 'SHSM_FPU_DISABLED', 'SHSM_FLUSH_DISABLED', 'SHSM_AI_CLOCK_NO_BUS', 'SHSM_SI_IDLE_REPLAY',
            'SHSM_DSP_DISABLED', 'SHSM_DSP_LOST_DMA', 'SHSM_DSP_LOST_MAIL', 'SHSM_MI_DISABLED', 'SHSM_MI_NO_SIZE_FIXTURE'):
        environment.pop(flag, None)
    if mode == 'disabled':
        environment['SHSM_RI_UART_DISABLED'] = '1'
    result = subprocess.run([str(output / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol',
        str(output / 'boot-quarantine.tsv'), str(private / 'sram-native/settings.bin')], env=environment,
        capture_output=True, text=True, timeout=30)
    assert result.returncode == build['results'][mode]['returnCode'] == 7 and not result.stderr
    fresh[mode] = validate(mode, result.stdout)
(output / 'audit.json').write_text(json.dumps({'result': 'RI_UART_BOOT_PASSES_NEXT_OS_GET_RESET_CODE_GUARD_RETAINED',
    'buildSha256': sha(output / 'boot.json'), 'auditorSha256': sha(Path(__file__)), 'boundaries': fresh,
    'limits': ['Next PC802194E0 is OSGetResetCode entry, not an exact refused load; source candidate80219504→CC003024.',
        'No new frame/menu/audio/full story/controller or physical Wii proof.']}, indent=2) + '\n')
print('PASS RI UART boot advances to OSGetResetCode; disabled restores EXI boundary; prior DSP/MI/clock/flush retained')

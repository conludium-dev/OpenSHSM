"""Audit two instruction-local accounting seams and replay actual arena-clear return."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess

root = Path('work/private-game/static-recomp')
output = root / 'mass-finite-mem2-boot'
base = root / 'mass-memory936-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'boot.json').read_text())
prior = json.loads((base / 'boot.json').read_text())
assert build['builderSha256'] == sha(Path('experiments/wii-static-recomp/build_finite_mem2_boot.py'))
assert build['baseBootSha256'] == sha(base / 'boot.json')
assert build['removedPolicy'] == ''
assert (output / 'boot-quarantine.tsv').read_bytes() == (base / 'boot-quarantine.tsv').read_bytes()
for row, old in zip(build['records'], prior['records']):
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    if row['file'] != 'output_63.cpp':
        assert row == old
    else:
        source = Path(row['source']).read_text()
        before = Path(old['source']).read_text()
        after_poll = '        if (nwii::runtime::experiment_finite_mem2_poll(ctx, process_pending_callbacks)) return;'
        after_return = '    nwii::runtime::experiment_finite_mem2_return(ctx);\n'
        assert source.count(after_poll) == source.count(after_return) == 1
        assert source.replace(after_poll, '        if (process_pending_callbacks(ctx)) return;').replace(after_return, '') == before
        assert '// 0x80213084: 4200FFF8\n    ctx.ctr--;' in source
        assert '// 0x80213088: 4E800020\n' + after_return in source
for path, digest in build['sourceHashes'].items():
    assert sha(Path(path)) == digest
assert build['executableSha256'] == sha(output / 'openshsm-mass-boot')
assert (output / 'finite_mem2_clear.h').read_bytes() == Path('experiments/wii-static-recomp/finite_mem2_clear.h').read_bytes()
fresh = {}
for mode in ('live', 'disabled'):
    environment = dict(os.environ)
    for name in ('SHSM_FPU_DISABLED', 'SHSM_FLUSH_DISABLED', 'SHSM_AI_CLOCK_NO_BUS', 'SHSM_SI_IDLE_REPLAY',
            'SHSM_DSP_DISABLED', 'SHSM_DSP_LOST_DMA', 'SHSM_DSP_LOST_MAIL', 'SHSM_MI_DISABLED', 'SHSM_MI_NO_SIZE_FIXTURE',
            'SHSM_RI_UART_DISABLED', 'SHSM_RESET_DISABLED', 'SHSM_DC_ZERO_DISABLED', 'SHSM_MEM2_LOADER_DISABLED', 'SHSM_FINITE_MEM2_DISABLED'):
        environment.pop(name, None)
    if mode == 'disabled':
        environment['SHSM_FINITE_MEM2_DISABLED'] = '1'
    result = subprocess.run([str(output / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol',
        str(output / 'boot-quarantine.tsv'), str(root / 'sram-native/settings.bin')], env=environment,
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 7 and not result.stderr
    log = result.stdout
    assert 'BOOT_MI phase=3 writes=3 realEntries=2 active=0 mask=16' in log
    assert 'BOOT_DSP commands=17 completed=2 accesses=24' in log
    boundary = next(line for line in log.splitlines() if line.startswith('BOOT_BOUNDARY '))
    if mode == 'live':
        assert re.fullmatch(r'BOOT_BOUNDARY pc=8021750c lr=80211630 msr=a032 calls=\d+ reason=SI external delivery producer/mask unverified', boundary)
        assert 'BOOT_FINITE_MEM2 steps=1765312 returned=1' in log
        assert 'BOOT_DCZERO lines=2346682' in log and 'BOOT_FLUSH entries=3 phase=0 barriers=3' in log
    else:
        assert re.fullmatch(r'BOOT_BOUNDARY pc=80213084 lr=80210ec8 msr=2032 calls=\d+ reason=Pre-service polling budget exceeded', boundary)
        assert 'BOOT_FINITE_MEM2 steps=0 returned=0' in log
        assert 'BOOT_FLUSH entries=2 phase=0 barriers=2' in log
    fresh[mode] = boundary
(output / 'audit.json').write_text(json.dumps({'result': 'BOOT_ORIGINAL_MEM2_FINITE_CLEAR_RETURNS_SI_ENABLE_BOUNDARY_RETAINED',
    'buildSha256': sha(output / 'boot.json'), 'auditorSha256': sha(Path(__file__)), 'freshBoundaries': fresh,
    'limits': ['Finite iterations retain original dcbz/CTR/branches; existing scheduler validates every backedge.',
        'Validated finite work charged separately, generic1M device polling limit unchanged.',
        'Measured emulator loader profile; no retail boot/first frame/menu/audio/controller acceptance.']}, indent=2) + '\n')
print('PASS fresh MEM1+MEM2 clears/flush3 return; finite progress1765312; disabled retains budget; SI enable refusal retained')

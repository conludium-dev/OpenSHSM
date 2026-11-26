"""Observe the refused interrupt-enable state without new hardware permission or generated-code edits."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
base = private / 'mass-finite-mem2-boot'
output = private / 'mass-interrupt-enable-observer'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((base / 'boot.json').read_text())
for name in ('mass_boot.cpp', 'loader-bat-seed.h', 'fp64-template-probe.h', 'mutable-template-probe.h',
        'hw_vi-clock.inc', 'vi-clock-backend.cpp', 'boot-quarantine.tsv', 'memory-protection-bat-plan.h',
        'memory_protection_frontend.h', 'dc_zero_frontend.h', 'reset_code_frontend.h', 'finite_mem2_clear.h'):
    (output / name).write_bytes((base / name).read_bytes())
wrapper = (base / 'boot-wrapper.cpp').read_text()
marker = '        return experiment_boot_poll(context);'
assert wrapper.count(marker) == 1
(output / 'boot-wrapper.cpp').write_text(wrapper.replace(marker,
    '        experiment_interrupt_enable_observe(context);\n' + marker))
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
sources = [output / 'boot-wrapper.cpp', output / 'vi-clock-backend.cpp', experiment / 'processor_adapter.cpp',
    experiment / 'ipc_reset_backend.cpp', experiment / 'ai_mask_backend.cpp', experiment / 'dsp_startup_backend.cpp',
    runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp', runtime / 'src/hw/mmio_dispatcher.cpp',
    runtime / 'src/core/event_scheduler.cpp']
exe = output / 'openshsm-mass-boot'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit',
    '-include', str(output / 'finite_mem2_clear.h'), '-include', str(experiment / 'interrupt_enable_observer.h'),
    '-DSHSM_SI_EXTERNAL_DELIVERY', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER', '-DSHSM_BOOT_INITIAL_MSR=0x30',
    '-I', str(output), '-I', str(experiment), '-I', str(private / 'mass-current'), '-I', str(runtime / 'include'),
    '-I', str(runtime / 'src/hw'), '-I', str(runtime.parent / 'nWiiAnalyzer/include'),
    *map(str, sources), *[row['object'] for row in build['records']], '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
environment = dict(os.environ)
for name in list(environment):
    if name.startswith('SHSM_'):
        environment.pop(name)
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(output / 'boot-quarantine.tsv'),
    str(private / 'sram-native/settings.bin')], env=environment, capture_output=True, text=True, timeout=30)
log_path = output / 'observed-boot.log'
log_path.write_text(result.stdout + result.stderr)
assert result.returncode == 7 and not result.stderr
(output / 'build.json').write_text(json.dumps({'result': 'INTERRUPT_ENABLE_OBSERVER_REQUIRES_AUDIT',
    'builderSha256': sha(Path(__file__)), 'baseBootSha256': sha(base / 'boot.json'), 'records': build['records'],
    'sourceHashes': {str(path): sha(path) for path in sources + [experiment / 'interrupt_enable_observer.h']},
    'executableSha256': sha(exe), 'logSha256': sha(log_path),
    'limits': ['Read-only snapshot before existing refusal; CPU/device stores and original source bodies unchanged.',
        'Cached SDK reads may populate cache; execution not resumed beyond refusal.']}, indent=2) + '\n')
print('\n'.join(line for line in result.stdout.splitlines() if line.startswith(('IRQ_ENABLE_', 'BOOT_BOUNDARY ', 'BOOT_FINITE_MEM2 '))))

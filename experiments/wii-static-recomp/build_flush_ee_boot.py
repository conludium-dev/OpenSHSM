"""Link the measured optional EE flush into existing startup; retain all original bodies."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
base = root / 'mass-ipc-startup-boot'
profile = root / 'flush-ee-profile'
output = root / 'mass-flush-ee-boot'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_flush_ee_native.py')], check=True)
build = json.loads((profile / 'build.json').read_text())
for path in profile.glob('*.h'):
    (output / path.name).write_bytes(path.read_bytes())
for name in ('processor_adapter.cpp', 'ipc_reset_backend.cpp', 'ai_mask_backend.cpp', 'dsp_startup_backend.cpp'):
    (output / name).write_bytes((profile / name).read_bytes())
for name in ('mass_boot.cpp', 'boot-wrapper.cpp', 'vi-clock-backend.cpp', 'hw_vi-clock.inc', 'boot-quarantine.tsv'):
    (output / name).write_bytes((base / name).read_bytes())
entry_path = output / 'mass_boot.cpp'
entry = entry_path.read_text()
marker = '    nwii::runtime::experiment_sram_attach_memory(context);'
assert entry.count(marker) == 1
entry_path.write_text(entry.replace(marker, marker + '\n    nwii::runtime::experimentFlushEe = !std::getenv("SHSM_FLUSH_EE_DISABLED");'))
sources = [output / 'boot-wrapper.cpp', output / 'vi-clock-backend.cpp', output / 'processor_adapter.cpp',
    output / 'ipc_reset_backend.cpp', output / 'ai_mask_backend.cpp', output / 'dsp_startup_backend.cpp',
    runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp', runtime / 'src/hw/mmio_dispatcher.cpp',
    runtime / 'src/core/event_scheduler.cpp']
exe = output / 'openshsm-mass-boot'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit',
    '-include', str(output / 'finite_mem2_clear.h'), '-include', str(output / 'interrupt_enable_observer.h'),
    '-DSHSM_SI_EXTERNAL_DELIVERY', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER', '-DSHSM_BOOT_INITIAL_MSR=0x30',
    '-I', str(output), '-I', str(experiment), '-I', str(root / 'mass-current'), '-I', str(runtime / 'include'),
    '-I', str(runtime / 'src/hw'), '-I', str(runtime.parent / 'nWiiAnalyzer/include'),
    *map(str, sources), *[row['object'] for row in build['records']], '-o', str(exe)],
    capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
(output / 'build.json').write_text(json.dumps({'result': 'EE_FLUSH_BOOT_REQUIRES_AUDIT',
    'builderSha256': sha(Path(__file__)), 'baseBuildSha256': sha(base / 'build.json'),
    'profileBuildSha256': sha(profile / 'build.json'), 'nativeProofSha256': sha(profile / 'comparison.json'),
    'records': build['records'], 'sourceHashes': {str(path): sha(path) for path in sources + [entry_path]},
    'headerHashes': {str(path): sha(path) for path in output.glob('*.h')},
    'executableSha256': sha(exe), 'quarantineSha256': sha(output / 'boot-quarantine.tsv')}, indent=2) + '\n')
print('EE flush startup linked; fresh boundary audit required')

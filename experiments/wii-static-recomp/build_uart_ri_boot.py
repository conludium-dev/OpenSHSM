"""Enable the verified RI UART profile in the existing memory-protection boot."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
base = private / 'mass-memory-protection-boot'
output = private / 'mass-uart-ri-boot'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_uart_ri_native.py')], check=True)
native = json.loads((private / 'uart-ri-native/build.json').read_text())
for name in ('loader-bat-seed.h', 'fp64-template-probe.h', 'mutable-template-probe.h', 'hw_vi-clock.inc',
        'vi-clock-backend.cpp', 'memory-protection-bat-plan.h', 'boot-quarantine.tsv'):
    (output / name).write_bytes((base / name).read_bytes())
entry = (base / 'mass_boot.cpp').read_text()
marker = '    nwii::runtime::experiment_sram_attach_memory(context);'
assert entry.count(marker) == 1
entry = entry.replace(marker, marker + '\n    nwii::runtime::experimentExiRiUart = !std::getenv("SHSM_RI_UART_DISABLED");')
(output / 'mass_boot.cpp').write_text(entry)
wrapper = output / 'boot-wrapper.cpp'
wrapper.write_bytes((base / 'boot-wrapper.cpp').read_bytes())
sources = [wrapper, output / 'vi-clock-backend.cpp', experiment / 'processor_adapter.cpp', experiment / 'ipc_reset_backend.cpp',
    experiment / 'ai_mask_backend.cpp', experiment / 'dsp_startup_backend.cpp', runtime / 'src/core/loader.cpp',
    runtime / 'src/hw/hw_pi.cpp', runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/core/event_scheduler.cpp']
exe = output / 'openshsm-mass-boot'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit',
    '-include', str(experiment / 'memory_protection_frontend.h'), '-DSHSM_SI_EXTERNAL_DELIVERY', '-DSHSM_PROCESSOR_ADAPTER',
    '-DSHSM_CACHE_ADAPTER', '-DSHSM_BOOT_INITIAL_MSR=0x30', '-I', str(output), '-I', str(experiment),
    '-I', str(private / 'mass-current'), '-I', str(runtime / 'include'), '-I', str(runtime / 'src/hw'),
    '-I', str(runtime.parent / 'nWiiAnalyzer/include'), *map(str, sources), *[row['object'] for row in native['records']],
    '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2500:]
results = {}
for mode in ('live', 'disabled'):
    environment = dict(os.environ)
    for name in ('SHSM_FPU_DISABLED', 'SHSM_FLUSH_DISABLED', 'SHSM_AI_CLOCK_NO_BUS', 'SHSM_SI_IDLE_REPLAY',
            'SHSM_DSP_DISABLED', 'SHSM_DSP_LOST_DMA', 'SHSM_DSP_LOST_MAIL', 'SHSM_MI_DISABLED', 'SHSM_MI_NO_SIZE_FIXTURE', 'SHSM_RI_UART_DISABLED'):
        environment.pop(name, None)
    if mode == 'disabled':
        environment['SHSM_RI_UART_DISABLED'] = '1'
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(output / 'boot-quarantine.tsv'),
        str(private / 'sram-native/settings.bin')], env=environment, capture_output=True, text=True, timeout=30)
    log = result.stdout + result.stderr
    (output / (mode + '-boot.log')).write_text(log)
    results[mode] = {'returnCode': result.returncode, 'logSha256': sha(output / (mode + '-boot.log'))}
    print(mode + ': ' + '\n'.join(line for line in log.splitlines() if line.startswith(('BOOT_BOUNDARY ', 'BOOT_MI ', 'BOOT_DSP ', 'BOOT_FLUSH '))))
(output / 'boot.json').write_text(json.dumps({'result': 'UART_RI_BOOT_REQUIRES_AUDIT', 'builderSha256': sha(Path(__file__)),
    'baseBootSha256': sha(base / 'boot.json'), 'nativeBuildSha256': sha(private / 'uart-ri-native/build.json'),
    'nativeProofSha256': sha(private / 'uart-ri-native/comparison.json'), 'records': native['records'],
    'sourceHashes': {str(path): sha(path) for path in sources}, 'entryBeforeSha256': sha(base / 'mass_boot.cpp'),
    'entryAfterSha256': sha(output / 'mass_boot.cpp'), 'executableSha256': sha(exe), 'results': results,
    'policySha256': sha(output / 'boot-quarantine.tsv'), 'limits': ['RI opt-in only the measured UART/helpers; existing devices/protocols remain guarded.',
        'Private SRAM/bus/size loader fixtures retained; no original frame/menu/full-game or physical UART proof.']}, indent=2) + '\n')

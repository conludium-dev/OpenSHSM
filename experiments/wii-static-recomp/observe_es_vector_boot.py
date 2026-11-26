"""Read only the existing guarded ES vector/output state, retaining every PPC object."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
base = root / 'mass-es-open-boot'
output = root / 'mass-es-vector-observer'
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'audit_es_open_boot.py')], check=True, capture_output=True, text=True)
build = json.loads((base / 'build.json').read_text())
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for path in base.glob('*.h'):
    (output / path.name).write_bytes(path.read_bytes())
for name in ('boot-wrapper.cpp', 'mass_boot.cpp', 'vi-clock-backend.cpp', 'hw_vi-clock.inc', 'processor_adapter.cpp',
    'ai_mask_backend.cpp', 'dsp_startup_backend.cpp', 'ipc_event_order_probe.cpp', 'ipc_reset_backend.cpp',
    'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'boot-quarantine.tsv'):
    (output / name).write_bytes((base / name).read_bytes())
entry_path = output / 'mass_boot.cpp'
entry = entry_path.read_text()
marker = '        std::cout << "BOOT_ES_LAYOUT "'
assert entry.count(marker) == 1
observer = r'''        if (context.pc == 0x80212ff4 && context.lr == 0x80242fc8 && context.msr == 0xa032 && context.gpr[29] == 0x935e0080) {
            std::cout << "ES_FLUSH_ARGUMENTS" << std::hex;
            for (unsigned index : {1u, 3u, 4u, 29u}) { std::cout << ' ' << context.gpr[index]; }
            std::cout << std::dec << '\n';
            for (bool cached : {false, true}) {
                const uint32_t vector = cached ? 0x8053fff0 : 0xc053fff0;
                std::cout << (cached ? "ES_VECTOR_CACHED" : "ES_VECTOR_PHYSICAL") << std::hex
                    << ' ' << nwii::runtime::bat_memory_read32(context, vector)
                    << ' ' << nwii::runtime::bat_memory_read32(context, vector + 4) << std::dec << '\n';
                std::cout << (cached ? "ES_OUTPUT_CACHED" : "ES_OUTPUT_PHYSICAL");
                for (unsigned offset = 0; offset < 32; ++offset) {
                    std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context,
                        (cached ? 0x8053ff20 : 0xc053ff20) + offset));
                }
                std::cout << '\n';
            }
        }
'''
entry_path.write_text(entry.replace(marker, observer + marker))
sources = [output / 'boot-wrapper.cpp', output / 'vi-clock-backend.cpp', output / 'processor_adapter.cpp',
    output / 'ai_mask_backend.cpp', output / 'dsp_startup_backend.cpp', runtime / 'src/core/loader.cpp',
    runtime / 'src/hw/hw_pi.cpp', runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/core/event_scheduler.cpp',
    root / 'stm-open-native/ios_kernel.cpp', output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp']
exe = output / 'es-vector-observer'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit',
    '-include', str(output / 'finite_mem2_clear.h'), '-include', str(output / 'interrupt_enable_observer.h'),
    '-DSHSM_SI_EXTERNAL_DELIVERY', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER', '-DSHSM_BOOT_INITIAL_MSR=0x30',
    '-I', str(output), '-I', str(experiment), '-I', str(root / 'mass-current'), '-I', str(runtime / 'include'),
    '-I', str(runtime / 'src/hw'), '-I', str(runtime.parent / 'nWiiAnalyzer/include'),
    *map(str, sources), *[row['object'] for row in build['records']], '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(output / 'boot-quarantine.tsv'),
    str(root / 'sram-native/settings.bin')], env=env, capture_output=True, text=True, timeout=30)
(output / 'observation.log').write_text(result.stdout + result.stderr)
assert result.returncode == 7 and not result.stderr
assert 'ES_VECTOR_CACHED 8053ff20 8' in result.stdout
assert 'BOOT_BOUNDARY pc=80212ff4 lr=80242fc8 msr=a032' in result.stdout
assert 'BOOT_STM_ASYNC dispatched=1 pending=1 6 1 324927520 4096 4796512 32 4796544 32' in result.stdout
lines = [line for line in result.stdout.splitlines() if line.startswith(('ES_', 'BOOT_BOUNDARY', 'BOOT_STM_ASYNC dispatched='))]
print('\n'.join(lines))
(output / 'observation.json').write_text(json.dumps({'builderSha256': sha(Path(__file__)), 'baseBuildSha256': sha(base / 'build.json'),
    'records': build['records'], 'sourceHashes': {str(path): sha(path) for path in sources + [entry_path, output / 'ipc_event_order_probe.cpp']},
    'headerHashes': {str(path): sha(path) for path in output.glob('*.h')}, 'executableSha256': sha(exe),
    'logSha256': sha(output / 'observation.log'), 'observations': lines,
    'limits': ['Native read-only diagnostic, all125 PPC objects/header permissions/backend unchanged; not original response or title-ID evidence.']}, indent=2) + '\n')

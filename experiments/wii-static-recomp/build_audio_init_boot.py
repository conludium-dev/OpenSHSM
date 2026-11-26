"""Connect the verified whole-function DSP startup adapter to the existing boot."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
base = private / 'mass-flush-syscall-boot'
output = private / 'mass-audio-init-boot'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_audio_init_native.py')], check=True)
native = json.loads((private / 'audio-init-native/build.json').read_text())
for name in ('loader-bat-seed.h', 'fp64-template-probe.h', 'mutable-template-probe.h', 'hw_vi-clock.inc', 'vi-clock-backend.cpp'):
    (output / name).write_bytes((base / name).read_bytes())
vi_source = output / 'vi-clock-backend.cpp'
vi_source.write_text('namespace nwii::runtime { uint64_t experiment_vi_unverified_time(); }\n' + vi_source.read_text())
entry_before = (base / 'mass_boot.cpp').read_text()
marker = '    nwii::runtime::experiment_sram_attach_memory(context);'
assert entry_before.count(marker) == 1
entry_after = entry_before.replace(marker, marker + '''
    nwii::runtime::EventScheduler::get().reset();
    nwii::runtime::hw::experimentDspStartup.enabled = !std::getenv("SHSM_DSP_DISABLED");
    nwii::runtime::hw::experimentDspStartup.lostDma = std::getenv("SHSM_DSP_LOST_DMA") != nullptr;
    nwii::runtime::hw::experimentDspStartup.lostMail = std::getenv("SHSM_DSP_LOST_MAIL") != nullptr;''')
(output / 'mass_boot.cpp').write_text(entry_after)
wrapper = output / 'boot-wrapper.cpp'
wrapper_body = '#include "dsp_startup_frontend.h"\n' + (base / 'boot-wrapper.cpp').read_text()
marker = '    const int result = original_boot_main(3, argv);'
assert wrapper_body.count(marker) == 1
wrapper_body = wrapper_body.replace(marker, marker + '''
    const auto& dsp = nwii::runtime::hw::experimentDspStartup;
    std::cout << "BOOT_DSP commands=" << dsp.command << " completed=" << dsp.completedDmas << " accesses=" << dsp.accesses.size() << "\\n";
    for (unsigned number = 0; number < dsp.accesses.size(); ++number) {
        std::cout << "BOOT_DSP_ACCESS";
        for (auto value : dsp.accesses[number]) { std::cout << ' ' << value; }
        std::cout << ' ' << dsp.accessTicks.at(number) << "\\n";
    }''')
wrapper.write_text(wrapper_body)
sources = [wrapper, output / 'vi-clock-backend.cpp', experiment / 'processor_adapter.cpp', experiment / 'ipc_reset_backend.cpp',
    experiment / 'ai_mask_backend.cpp', experiment / 'dsp_startup_backend.cpp', runtime / 'src/core/loader.cpp',
    runtime / 'src/hw/hw_pi.cpp', runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/core/event_scheduler.cpp']
exe = output / 'openshsm-mass-boot'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit',
    '-include', str(experiment / 'dsp_startup_frontend.h'), '-DSHSM_SI_EXTERNAL_DELIVERY', '-DSHSM_PROCESSOR_ADAPTER',
    '-DSHSM_CACHE_ADAPTER', '-DSHSM_BOOT_INITIAL_MSR=0x30', '-I', str(output), '-I', str(experiment),
    '-I', str(private / 'mass-current'), '-I', str(runtime / 'include'), '-I', str(runtime / 'src/hw'),
    '-I', str(runtime.parent / 'nWiiAnalyzer/include'), *map(str, sources), *[row['object'] for row in native['records']],
    '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
policy = output / 'boot-quarantine.tsv'
policy.write_bytes((base / 'boot-quarantine.tsv').read_bytes())
results = {}
for mode, flag in [('live', None), ('disabled', 'SHSM_DSP_DISABLED'), ('lost-dma', 'SHSM_DSP_LOST_DMA'), ('lost-mail', 'SHSM_DSP_LOST_MAIL')]:
    environment = dict(os.environ)
    for name in ('SHSM_FPU_DISABLED', 'SHSM_FLUSH_DISABLED', 'SHSM_AI_CLOCK_NO_BUS', 'SHSM_SI_IDLE_REPLAY',
            'SHSM_DSP_DISABLED', 'SHSM_DSP_LOST_DMA', 'SHSM_DSP_LOST_MAIL'):
        environment.pop(name, None)
    if flag:
        environment[flag] = '1'
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy),
        str(private / 'sram-native/settings.bin')], env=environment, capture_output=True, text=True, timeout=30)
    log = result.stdout + result.stderr
    (output / (mode + '-boot.log')).write_text(log)
    results[mode] = {'returnCode': result.returncode, 'logSha256': sha(output / (mode + '-boot.log'))}
    print(mode + ': ' + '\n'.join(line for line in log.splitlines() if line.startswith(('BOOT_BOUNDARY ', 'BOOT_FLUSH ', 'BOOT_PC_CLOCK ', 'BOOT_DSP '))))
(output / 'boot.json').write_text(json.dumps({'result': 'AUDIO_INIT_BOOT_REQUIRES_AUDIT', 'builderSha256': sha(Path(__file__)),
    'baseBootSha256': sha(base / 'boot.json'), 'nativeBuildSha256': sha(private / 'audio-init-native/build.json'),
    'nativeProofSha256': sha(private / 'audio-init-native/comparison.json'), 'records': native['records'],
    'sourceHashes': {str(path): sha(path) for path in sources}, 'entryBeforeSha256': sha(base / 'mass_boot.cpp'),
    'entryAfterSha256': sha(output / 'mass_boot.cpp'), 'executableSha256': sha(exe), 'results': results,
    'policySha256': sha(policy), 'limits': ['Existing boot dispatcher/backend/cache/scheduler reused; measured startup HLE only.',
        'No DSP instruction emulation/audio playback or first frame/menu proof; unsupported next access remains guarded.']}, indent=2) + '\n')

"""Connect verified memory protection to the existing experimental boot."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
base = private / 'mass-audio-init-boot'
output = private / 'mass-memory-protection-boot'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_memory_protection_native.py')], check=True)
native = json.loads((private / 'memory-protection-native/build.json').read_text())
for name in ('loader-bat-seed.h', 'fp64-template-probe.h', 'mutable-template-probe.h', 'hw_vi-clock.inc', 'vi-clock-backend.cpp'):
    (output / name).write_bytes((base / name).read_bytes())
(output / 'memory-protection-bat-plan.h').write_bytes((private / 'memory-protection-native/memory-protection-bat-plan.h').read_bytes())
entry_before = (base / 'mass_boot.cpp').read_text()
marker = '    nwii::runtime::experiment_sram_attach_memory(context);'
assert entry_before.count(marker) == 1
entry_after = entry_before.replace(marker, marker + '''
    nwii::runtime::experimentMemoryProtection.enabled = !std::getenv("SHSM_MI_DISABLED");
    nwii::runtime::hw::experiment_register_mi_protection(nwii::runtime::MMIODispatcher::get());''')
marker = '    context.gpr.fill(0);'
assert entry_after.count(marker) == 2
location = entry_after.index(marker, entry_after.index('nwii::loader::Executable executable;'))
entry_after = entry_after[:location] + '''    if (!std::getenv("SHSM_MI_NO_SIZE_FIXTURE")) {
        for (const auto& seed : std::array<std::array<uint32_t, 2>, 4>{{
            {0x3100, 0x01800000}, {0x3104, 0x01800000}, {0x311c, 0x04000000}, {0x3120, 0x93400000}}}) {
            context.mmu.write32(seed[0], seed[1]);
        }
    }
''' + entry_after[location:]
(output / 'mass_boot.cpp').write_text(entry_after)
wrapper = output / 'boot-wrapper.cpp'
wrapper_body = '#include "memory_protection_frontend.h"\n' + (base / 'boot-wrapper.cpp').read_text()
marker = '    const int result = original_boot_main(3, argv);'
assert wrapper_body.count(marker) == 1
wrapper_body = wrapper_body.replace(marker, marker + '''
    const auto& mi = nwii::runtime::experimentMemoryProtection;
    std::cout << "BOOT_MI phase=" << mi.phase << " writes=" << mi.writes.size() << " realEntries=" << mi.realEntries
              << " active=" << (mi.realOwner != nullptr) << " mask=" << nwii::runtime::hw::experimentMiMask << "\\n";''')
wrapper.write_text(wrapper_body)
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
assert result.returncode == 0, result.stderr[-3000:]
policy = output / 'boot-quarantine.tsv'
policy_body = (base / 'boot-quarantine.tsv').read_text()
removed_policy = []
for address in ('80218070', '802180F0'):
    entry = address + '\t//_unhandled\n'
    assert policy_body.count(entry) == 1
    policy_body = policy_body.replace(entry, '')
    removed_policy.append(entry)
policy.write_text(policy_body)
results = {}
for mode, flag in [('live', None), ('disabled', 'SHSM_MI_DISABLED'), ('no-size', 'SHSM_MI_NO_SIZE_FIXTURE')]:
    environment = dict(os.environ)
    for name in ('SHSM_FPU_DISABLED', 'SHSM_FLUSH_DISABLED', 'SHSM_AI_CLOCK_NO_BUS', 'SHSM_SI_IDLE_REPLAY',
            'SHSM_DSP_DISABLED', 'SHSM_DSP_LOST_DMA', 'SHSM_DSP_LOST_MAIL', 'SHSM_MI_DISABLED', 'SHSM_MI_NO_SIZE_FIXTURE'):
        environment.pop(name, None)
    if flag:
        environment[flag] = '1'
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy),
        str(private / 'sram-native/settings.bin')], env=environment, capture_output=True, text=True, timeout=30)
    log = result.stdout + result.stderr
    (output / (mode + '-boot.log')).write_text(log)
    results[mode] = {'returnCode': result.returncode, 'logSha256': sha(output / (mode + '-boot.log'))}
    print(mode + ': ' + '\n'.join(line for line in log.splitlines() if line.startswith(('BOOT_BOUNDARY ', 'BOOT_MI ', 'BOOT_DSP ', 'BOOT_FLUSH '))))
(output / 'boot.json').write_text(json.dumps({'result': 'MEMORY_PROTECTION_BOOT_REQUIRES_AUDIT', 'builderSha256': sha(Path(__file__)),
    'baseBootSha256': sha(base / 'boot.json'), 'nativeBuildSha256': sha(private / 'memory-protection-native/build.json'),
    'nativeProofSha256': sha(private / 'memory-protection-native/comparison.json'), 'records': native['records'],
    'sourceHashes': {str(path): sha(path) for path in sources}, 'entryBeforeSha256': sha(base / 'mass_boot.cpp'),
    'entryAfterSha256': sha(output / 'mass_boot.cpp'), 'executableSha256': sha(exe), 'results': results,
    'policySha256': sha(policy), 'removedPolicy': removed_policy, 'planSha256': sha(output / 'memory-protection-bat-plan.h'),
    'limits': ['Prepared loader size fields24MB/64MB/93400000 are disclosed PC lab adaptation.',
        'Existing dispatcher/BAT/MI storage retained; no protection faults/MI IRQ or first screen/menu/audio proof.']}, indent=2) + '\n')

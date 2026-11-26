"""Opt-in measured STM exchange on the existing whole-DOL startup path."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
profile = root / 'stm-send-cycle'
base = root / 'mass-flush-packet-boot'
output = root / 'mass-stm-startup-boot'
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_stm_send_native.py')], check=True)
build = json.loads((profile / 'attempt.json').read_text())
base_build = json.loads((base / 'build.json').read_text())
for path, digest in {**base_build['sourceHashes'], **base_build['headerHashes']}.items():
    assert sha(Path(path)) == digest
for path in profile.glob('*.h'):
    (output / path.name).write_bytes(path.read_bytes())
for name in ('mass_boot.cpp', 'boot-wrapper.cpp', 'vi-clock-backend.cpp', 'hw_vi-clock.inc', 'boot-quarantine.tsv'):
    (output / name).write_bytes((base / name).read_bytes())
for name in ('processor_adapter.cpp', 'ai_mask_backend.cpp', 'dsp_startup_backend.cpp',
    'ipc_event_order_probe.cpp', 'ipc_reset_backend.cpp'):
    (output / name).write_bytes((profile / name).read_bytes())
front = (output / 'ipc_ack_frontend.h').read_text()
front = front.replace('inline unsigned stmSubmitted = 0;', 'inline unsigned stmSubmitted = 0;\ninline bool experimentBootStm = false;')
front = front.replace('state.ppcControl != 0x30', '(state.ppcControl != 0x30 && state.ppcControl != 0x38)')
front = front.replace('hw::pi_intsr.load() != 0x10000', '(hw::pi_intsr.load() != 0 && hw::pi_intsr.load() != 0x10000)')
marker = '    if (!experimentStmIrq) { experiment_ipc_startup_store(context, address, value); return; }'
assert front.count(marker) == 1
front = front.replace(marker, '''    if (!experimentStmIrq && experimentBootStm && context.pc == 0x80241c30 &&
        context.lr == 0x80242384 && address == 0xcd000000 && context.msr == 0x2032 &&
        value == 0x135e0020 && !stmSubmitted) {
        const auto state = hw::experiment_ipc_snapshot();
        if (state.ppcControl != 0x38 || state.ppcMessage || state.armMessage || state.armControl || state.delay ||
            state.ppcMask != 0x40000000 || hw::pi_intmr.load() != 0x40f8 || hw::pi_intsr.load() != 0 ||
            context.in_callback || context.callback_depth || !context.backup_stack.empty()) {
            throw std::runtime_error("Startup STM activation state unverified: control=" + std::to_string(state.ppcControl) +
                " message=" + std::to_string(state.ppcMessage) + " arm=" + std::to_string(state.armMessage) +
                " armControl=" + std::to_string(state.armControl) + " delay=" + std::to_string(state.delay) +
                " mask=" + std::to_string(state.ppcMask) + " piCause=" + std::to_string(hw::pi_intsr.load()) +
                " piMask=" + std::to_string(hw::pi_intmr.load()));
        }
        experimentStmIrq = true;
    }
''' + marker)
(output / 'ipc_ack_frontend.h').write_text(front)
host = (profile / 'stm-irq-attempt-host.cpp').read_text()
start = host.index('inline unsigned stmProduced = 0;')
end = host.index('bool process_pending_callbacks', start)
support = host[start:end]
wrapper_path = output / 'boot-wrapper.cpp'
wrapper = wrapper_path.read_text()
wrapper = '''#include "ipc_ack_frontend.h"
#define main unused_stm_event_main
#include "ipc_event_order_probe.cpp"
#undef main
#include "ipc_open_packet.h"
#include "runtime/devices.h"
namespace nwii::runtime {
''' + support + '\n}\n' + wrapper
marker = '    const int result = original_boot_main(3, argv);'
assert wrapper.count(marker) == 1
wrapper = wrapper.replace(marker, '''    nwii::runtime::experimentBootStm = !std::getenv("SHSM_STM_STARTUP_DISABLED");
    nwii::runtime::IOSKernel::get().init();
    nwii::runtime::IOSKernel::get().register_device(nwii::runtime::devices::create_stm_device());
    nwii::runtime::MMIODispatcher::get().register_region(0xcd000000, 0xcd000003,
        [](uint32_t) -> uint32_t { throw std::runtime_error("Startup IPC message read unverified"); },
        [](uint32_t address, uint32_t value) {
            if (address != 0xcd000000) { throw std::runtime_error("Startup IPC message write alignment unverified"); }
            nwii::runtime::hw::ipc_ppc_msg = value;
        });
''' + marker + '''
    std::cout << "BOOT_STM submitted=" << nwii::runtime::stmSubmitted << " produced=" << nwii::runtime::stmProduced << '\\n';
''')
marker = '        return experiment_boot_poll(context);'
assert wrapper.count(marker) == 1
wrapper = wrapper.replace(marker, '''        if (experimentStmIrq && (context.msr & 0x8000)) {
            EventScheduler::get().advance(context, EventScheduler::get().now() + 1);
            hw::experiment_ipc_irq_update();
        }
''' + marker)
marker = '    original_trace_call(address, context);'
assert wrapper.count(marker) == 1
wrapper = wrapper.replace(marker, '''    if (address == 0x80242550 && stmProduced == 1 && stmSubmitted == 2) {
        std::cout << "BOOT_STM_FIRST_COMPLETE" << std::hex;
        for (uint32_t location : {0x8052ab20u, 0x80528b70u, 0x8052ab00u, 0x8052ab04u, 0x8052ab08u,
            0x800000c0u, 0x800000d4u, 0x800000d8u, 0x800000e4u, 0x80492920u,
            0x804b2a80u, 0x804b2a84u, 0x804b2a88u, 0x804b2a8cu,
            0x804b2b44u, 0x804b2b4cu, 0x935e0004u}) {
            std::cout << ' ' << location << ' ' << bat_memory_read32(context, location);
        }
        std::cout << std::dec << '\\n';
        for (bool cached : {false, true}) {
            std::cout << (cached ? "BOOT_STM_FIRST_CACHED" : "BOOT_STM_FIRST_PHYSICAL");
            for (unsigned index = 0; index < 64; ++index) {
                std::cout << ' ' << unsigned(bat_memory_read8(context, 0x135e0020 + index +
                    (cached ? 0x80000000 : 0xc0000000)));
            }
            std::cout << '\\n';
        }
    }
''' + marker)
wrapper_path.write_text(wrapper)
entry_path = output / 'mass_boot.cpp'
entry = entry_path.read_text()
marker = '        std::cout << "BOOT_REGISTERS";'
assert entry.count(marker) == 1
entry = entry.replace(marker, '''        if (nwii::runtime::experimentStmIrq && (context.msr & 0x10)) {
            std::cout << "BOOT_STM_LAYOUT" << std::hex;
            for (uint32_t address : {0x800000c0u, 0x800000d4u, 0x800000d8u, 0x800000e4u,
                0x8052ab00u, 0x8052ab04u, 0x8052ab08u, 0x80492920u, 0x804927f0u,
                0x804b2a80u, 0x804b2a84u, 0x804b2a88u, 0x804b2a8cu}) {
                std::cout << ' ' << address << ' ' << nwii::runtime::bat_memory_read32(context, address);
            }
            std::cout << std::dec << '\\n';
            if (context.pc == 0x80241c30 && context.lr == 0x80242384 &&
                context.gpr[4] >= 0x135e0020 && context.gpr[4] <= 0x135e03e0 && !(context.gpr[4] & 31)) {
                const uint32_t physical = context.gpr[4];
                const auto* packet = context.mmu.get_ptr(physical);
                std::cout << "BOOT_STM_NEXT_PACKET " << physical;
                for (unsigned index = 0; index < 64; ++index) {
                    std::cout << ' ' << unsigned(packet[index]);
                }
                std::cout << '\\n';
                const auto path = nwii::runtime::experiment_ipc_be32(packet + 12);
                if (nwii::runtime::experiment_ipc_be32(packet) == 1 && path >= 0x400000 && path < 0x17fff00) {
                    std::cout << "BOOT_STM_NEXT_PATH ";
                    for (unsigned index = 0; index < 64; ++index) {
                        const auto byte = *context.mmu.get_ptr(path + index);
                        if (!byte) { break; }
                        if (byte < 32 || byte >= 127) { break; }
                        std::cout << char(byte);
                    }
                    std::cout << '\\n';
                }
            }
        }
''' + marker)
entry_path.write_text(entry)
records = [dict(row) for row in build['records']]
row = next(row for row in records if row['file'] == 'output_67.cpp')
target = output / row['file']
target.write_bytes(Path(row['source']).read_bytes())
obj = output / (row['file'] + '.o')
includes = ['-include', str(output / 'finite_mem2_clear.h'), '-I', str(output), '-I', str(experiment),
    '-I', str(root / 'mass-current'), '-I', str(runtime / 'include')]
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-DSHSM_SI_EXTERNAL_DELIVERY',
    *includes, '-include', str(output / 'ipc_ack_frontend.h'), '-c', str(target), '-o', str(obj)],
    capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
row.update(source=str(target), sourceSha256=sha(target), object=str(obj), objectSha256=sha(obj))
sources = [wrapper_path, output / 'vi-clock-backend.cpp', output / 'processor_adapter.cpp',
    output / 'ai_mask_backend.cpp', output / 'dsp_startup_backend.cpp', runtime / 'src/core/loader.cpp',
    runtime / 'src/hw/hw_pi.cpp', runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/core/event_scheduler.cpp',
    root / 'stm-open-native/ios_kernel.cpp', runtime / 'src/hle/devices/stm_device.cpp']
exe = output / 'openshsm-mass-boot'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit',
    *includes, '-include', str(output / 'interrupt_enable_observer.h'), '-DSHSM_SI_EXTERNAL_DELIVERY', '-DSHSM_PROCESSOR_ADAPTER',
    '-DSHSM_CACHE_ADAPTER', '-DSHSM_BOOT_INITIAL_MSR=0x30',
    '-I', str(runtime / 'src/hw'), '-I', str(runtime.parent / 'nWiiAnalyzer/include'),
    *map(str, sources), *[row['object'] for row in records], '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
(output / 'build.json').write_text(json.dumps({'builderSha256': sha(Path(__file__)), 'baseBuildSha256': sha(base / 'build.json'),
    'profileAttemptSha256': sha(profile / 'attempt.json'), 'profileComparisonSha256': sha(profile / 'comparison.json'),
    'records': records, 'sourceHashes': {str(path): sha(path) for path in sources + [entry_path]},
    'headerHashes': {str(path): sha(path) for path in output.glob('*.h')}, 'executableSha256': sha(exe),
    'quarantineSha256': sha(output / 'boot-quarantine.tsv'), 'limits': [
        'Private opt-in existing startup; original DOL entrypoint/resources/context/queues/packet creation, no host request seeding.',
        'Measured STM mode0 OPEN only, cold control38; other commands/devices and next startup boundary remain guarded.',
        'ACK/reply event ticks/PI projection are PC adaptations, not original cycle timing or first-frame proof.']}, indent=2) + '\n')
print('Whole startup STM candidate linked; fresh execution/audit required')

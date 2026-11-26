"""Attempt whole original __IPCSend with real scheduled ACK/reply and actual sleep."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
base = root / 'stm-sleep-native'
variant = 'stm-send-missing' if '--missing-producer' in sys.argv else 'stm-send-wrong' if '--wrong-result' in sys.argv else 'stm-send-cycle'
output = root / variant
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_stm_sleep_native.py')], check=True)
build = json.loads((base / 'attempt.json').read_text())
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for path in base.glob('*.h'):
    (output / path.name).write_bytes(path.read_bytes())
for name in ('mass_boot.cpp', 'processor_adapter.cpp', 'ai_mask_backend.cpp', 'dsp_startup_backend.cpp',
    'ipc_event_order_probe.cpp', 'ipc_reset_backend.cpp'):
    (output / name).write_bytes((base / name).read_bytes())
frontend = (output / 'ipc_ack_frontend.h').read_text()
frontend = frontend.replace('namespace nwii::runtime {', '''namespace nwii::runtime {
inline unsigned stmSubmitted = 0;
void experiment_stm_submit(CPUContext& context, uint32_t request);
''', 1)
frontend = frontend.replace('    experiment_ipc_ack_access(context, address);\n    const auto ipc = hw::experiment_ipc_snapshot();', '''    if (context.pc == 0x80241c20 && context.lr == 0x802423bc && address == 0xcd000004 &&
        experimentStmIrq && context.msr == 0x2032 && stmSubmitted == 1) {
        const auto mapping = resolve_reference_bat(bat_context(context).dbat, bat_context(context).hid4, context.msr, address, false);
        const auto state = hw::experiment_ipc_snapshot();
        if (mapping.physical != 0x0d000004 || mapping.slot != 1 || mapping.wimg != 5 ||
            state.ppcControl != 0x30 || state.armMessage || state.armControl || state.delay ||
            state.ppcMask != 0x40000000 || hw::pi_intmr.load() != 0x40f8) {
            throw std::runtime_error("STM sender control read unverified");
        }
        return state.ppcControl;
    }
    experiment_ipc_ack_access(context, address);
    const auto ipc = hw::experiment_ipc_snapshot();''', 1)
marker = '    if (!experimentStmIrq) { experiment_ipc_startup_store(context, address, value); return; }'
assert frontend.count(marker) == 1
frontend = frontend.replace(marker, marker + '''
    if (context.pc == 0x80241c30 && context.msr == 0x2032 &&
        (context.lr == 0x80242384 || context.lr == 0x802423cc)) {
        const auto state = hw::experiment_ipc_snapshot();
        const auto mapping = resolve_reference_bat(bat_context(context).dbat, bat_context(context).hid4, context.msr, address, true);
        if (mapping.physical != (address & 0x1fffffffu) || mapping.slot != 1 || mapping.wimg != 5 ||
            memory_context(context).hid0 != 0xc200 || state.ppcControl != 0x30 || state.armMessage ||
            state.armControl || state.delay || state.ppcMask != 0x40000000 || hw::pi_intmr.load() != 0x40f8 ||
            hw::pi_intsr.load() != 0x10000 || context.in_callback || context.callback_depth ||
            !context.backup_stack.empty()) {
            throw std::runtime_error("STM sender write profile unverified");
        }
        if (context.lr == 0x80242384 && address == 0xcd000000 && !stmSubmitted && !state.ppcMessage &&
            value >= 0x135e0020 && value <= 0x135e03e0 && !(value & 31)) {
            MMIODispatcher::get().write32(address, value);
            ++stmSubmitted;
            return;
        }
        if (context.lr == 0x802423cc && address == 0xcd000004 && stmSubmitted == 1 && value == 0x31) {
            experiment_stm_submit(context, state.ppcMessage);
            ++stmSubmitted;
            return;
        }
        throw std::runtime_error("STM sender caller/value unverified");
    }
''', 1)
(output / 'ipc_ack_frontend.h').write_text(frontend)
host = (base / 'stm-irq-attempt-host.cpp').read_text()
host = host.replace('extern "C" void run_game(nwii::runtime::CPUContext&);', '''extern "C" void run_game(nwii::runtime::CPUContext&);
void func_80243570(nwii::runtime::CPUContext&);
void func_802438A0(nwii::runtime::CPUContext&);
''')
marker = '        auto* packet = context.mmu.get_ptr(physical);'
assert host.count(marker) == 1
host = host.replace(marker, '''        context.gpr[1] = 0x80540000;
        context.gpr[13] = 0x8052e720;
        context.gpr[3] = (physical | 0x80000000) - 32;
        context.gpr[4] = 4096;
        context.pc = 0x80243570;
        context.lr = 0x807f1000;
        func_80243570(context);
        if (context.pc != 0x807f1000 || context.gpr[3] != 0) { return 10; }
        bat_memory_write32(context, 0x80528b74, 0);
        context.gpr[3] = 0;
        context.gpr[4] = 64;
        context.gpr[5] = 32;
        context.pc = 0x802438a0;
        context.lr = 0x807f1000;
        func_802438A0(context);
        if (context.pc != 0x807f1000 || context.gpr[3] != (physical | 0x80000000)) { return 11; }
''' + marker)
host = host.replace('        std::memset(packet, 0, 64);', '''        for (unsigned offset = 0; offset < 64; offset += 4) {
            bat_memory_write32(context, (physical | 0x80000000) + offset, 0);
        }''')
host = host.replace('        experiment_ipc_store_be32(packet, 1);',
    '        bat_memory_write32(context, physical | 0x80000000, 1);')
host = host.replace('        experiment_ipc_store_be32(packet + 12, pathAddress);',
    '        bat_memory_write32(context, (physical | 0x80000000) + 12, pathAddress);')
host = host.replace('        hw::pi_intsr = 0x14000;', '        hw::pi_intsr = 0x10000;')
host = host.replace('        hw::ipc_ppc_ctrl = 0x32;', '        hw::ipc_ppc_ctrl = 0x30;')
host = host.replace('        hw::experimentPpcFlags = 0x40000000;', '        hw::experimentPpcFlags = 0;')
host = host.replace('        hw::ipc_ppc_msg = physical;', '        hw::ipc_ppc_msg = 0;')
host = host.replace('        hw::register_pi(MMIODispatcher::get());',
    '        hw::register_pi(MMIODispatcher::get());\n        hw::register_ipc(MMIODispatcher::get());')
host = host.replace('        context.gpr[3] = (physical | 0x80000000) + 44;\n        context.pc = 0x8021b4e0;',
    '        context.gpr[3] = physical | 0x80000000;\n        context.gpr[4] = 0;\n        context.pc = 0x802421f0;')
host = host.replace('{0x80528b70, 0}', '{0x80528b70, 1}')
start = host.index('        hw::experiment_fixture_reply_after(physical, 1,')
end = host.index('        try { run_game(context); }', start)
host = host[:start] + '''        stmSubmitted = 0;
        bat_context(context).flushSyscall = true;
        for (unsigned slot = 0; slot < 7; ++slot) {
            bat_memory_write32(context, 0x80000c00 + slot * 4, bat_memory_read32(context, 0x8021a120 + slot * 4));
        }
''' + host[end:]
marker = 'inline unsigned stmProduced = 0;'
host = host.replace(marker, marker + '''
void experiment_stm_submit(CPUContext&, uint32_t request) {
    hw::ipc_ppc_ctrl = 0x31;
    EventScheduler::get().schedule_after(1, [](CPUContext&, uint64_t) {
        hw::ipc_ppc_ctrl = (hw::ipc_ppc_ctrl & ~1u) | 2;
    });
    hw::experiment_fixture_reply_after(request, 2, [request](CPUContext& active, uint64_t) {
#ifndef SHSM_MISSING_STM_REPLY
        experiment_ipc_open_packet(active, request);
#ifdef SHSM_WRONG_STM_REPLY
        experiment_ipc_store_be32(active.mmu.get_ptr(request) + 4, 0x42);
#endif
        ++stmProduced;
#endif
    });
}
''')
host = host.replace('STM_SLEEP_CASE', 'STM_SEND_CASE')
host = host.replace('        for (uint32_t address : {0x80528b70u,',
    '        std::cout << \' \' << context.gpr[3] << \' \' << bat_context(context).flushEntries;\n        for (uint32_t address : {0x80528b70u,')
host = host.replace('        for (bool cached : {false, true}) {', '''        std::cout << "STM_SEND_HEAP " << index;
        for (uint32_t address : {0x804b2b40u, 0x804b2b44u, 0x804b2b48u, 0x804b2b4cu,
            (physical | 0x80000000) - 32, (physical | 0x80000000) - 28,
            0x804b2a80u, 0x804b2a84u, 0x804b2a88u, 0x804b2a8cu}) {
            std::cout << ' ' << bat_memory_read32(context, address);
        }
        std::cout << '\\n';
        for (bool cached : {false, true}) {''')
host = host.replace('            << \' \' << siExternalEntries << \' \' << stmProduced;',
    '            << \' \' << siExternalEntries << \' \' << stmProduced << \' \' << stmSubmitted;')
host_path = output / 'stm-irq-attempt-host.cpp'
host_path.write_text(host)
records = [dict(row) for row in build['records']]
row = next(row for row in records if row['file'] == 'output_67.cpp')
target = output / row['file']
target.write_bytes(Path(row['source']).read_bytes())
obj = output / (row['file'] + '.o')
includes = ['-include', str(output / 'finite_mem2_clear.h'), '-I', str(output), '-I', str(experiment),
    '-I', str(root / 'mass-current'), '-I', str(runtime / 'include')]
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-DSHSM_SI_EXTERNAL_DELIVERY', '-DSHSM_STM_ACK_MMIO',
    *includes, '-include', str(output / 'ipc_ack_frontend.h'), '-c', str(target), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
row.update(source=str(target), sourceSha256=sha(target), object=str(obj), objectSha256=sha(obj))
sources = [host_path, output / 'processor_adapter.cpp', output / 'ai_mask_backend.cpp', output / 'dsp_startup_backend.cpp',
    runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp', runtime / 'src/hw/mmio_dispatcher.cpp',
    runtime / 'src/core/event_scheduler.cpp', root / 'stm-open-native/ios_kernel.cpp', runtime / 'src/hle/devices/stm_device.cpp']
macro = ['-DSHSM_MISSING_STM_REPLY'] if variant == 'stm-send-missing' else ['-DSHSM_WRONG_STM_REPLY'] if variant == 'stm-send-wrong' else []
exe = output / 'stm-send-cycle'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit',
    '-DSHSM_SI_EXTERNAL_DELIVERY', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER', '-DSHSM_STM_ACK_MMIO',
    *macro, *includes, '-I', str(runtime / 'src/hw'), '-I', str(runtime.parent / 'nWiiAnalyzer/include'),
    *map(str, sources), *[row['object'] for row in records], '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'build.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], capture_output=True, text=True, timeout=30)
(output / 'native.log').write_text(result.stdout + result.stderr)
(output / 'attempt.json').write_text(json.dumps({'builderSha256': sha(Path(__file__)), 'baseAttemptSha256': sha(base / 'attempt.json'),
    'records': records, 'sourceHashes': {str(path): sha(path) for path in sources},
    'headerHashes': {str(path): sha(path) for path in output.glob('*.h')}, 'executableSha256': sha(exe),
    'returnCode': result.returncode, 'logSha256': sha(output / 'native.log'), 'limits': [
        'Actual original __IPCSend attempted; no successful combined lifecycle claim without original oracle comparison.',
        'Existing shared IPC/EventScheduler/kernel/cache profile; ACK/reply scheduling is a disclosed PC timing adaptation.',
        'Original heap creation and allocation prepare the packet; not whole IOS_Open caller or boot integration.',
        'Production startup/release unchanged.']}, indent=2) + '\n')
print(result.stdout[-6000:] + result.stderr[-1000:])
assert result.returncode in (0, 7)

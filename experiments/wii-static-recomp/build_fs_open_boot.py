"""Integrate exactly the measured fourth FS OPEN into the existing private boot."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
base = root / 'mass-exi-sync-ee-boot'
output = root / 'mass-fs-open-boot'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
for verifier in ('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py'):
    subprocess.run(['python3', str(experiment / verifier)], check=True)
build = json.loads((base / 'build.json').read_text())
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for path in base.glob('*.h'):
    (output / path.name).write_bytes(path.read_bytes())
for name in ('boot-wrapper.cpp', 'mass_boot.cpp', 'vi-clock-backend.cpp', 'hw_vi-clock.inc', 'processor_adapter.cpp',
    'ai_mask_backend.cpp', 'dsp_startup_backend.cpp', 'ipc_event_order_probe.cpp', 'ipc_reset_backend.cpp',
    'stm_device.cpp', 'boot-quarantine.tsv'):
    (output / name).write_bytes((base / name).read_bytes())

def replace(path, old, new, count=1):
    text = path.read_text()
    assert text.count(old) == count, (path, old, text.count(old))
    path.write_text(text.replace(old, new))

packet = output / 'ipc_open_packet.h'
replace(packet, '    if (!length || physical < 0x00400000u', '''    if (length == 1 && physical >= 0x135e1000 && physical < 0x135e1008) {
        return context.mmu.get_ptr(physical);
    }
    if (!length || physical < 0x00400000u''')
replace(packet, 'path != "/dev/openshsm_missing")', 'path != "/dev/openshsm_missing" && path != "/dev/fs")')
replace(packet, '(path == "/dev/stm/immediate" || path == "/dev/stm/eventhook")', '(path == "/dev/stm/immediate" || path == "/dev/stm/eventhook" || path == "/dev/fs")')
front = output / 'ipc_ack_frontend.h'
replace(front, '#include "ipc_open_packet.h"', '#include "ipc_open_packet.h"\n#include "stm_async_dispatch.h"')
replace(front, 'void experiment_stm_submit', '''inline bool experiment_fs_prior_arm(uint32_t message, uint32_t arm) {
    return (stmSubmitted == 7 || stmSubmitted == 8) && message == 0x135e0080 && arm == 0x135e0020 &&
        devices::experiment_stm_pending() && devices::experiment_stm_pending()->req_addr == 0x135e0020;
}
void experiment_stm_submit''')
replace(front, '(snapshot.armMessage && snapshot.armMessage != snapshot.ppcMessage)',
    '(snapshot.armMessage && snapshot.armMessage != snapshot.ppcMessage && !experiment_fs_prior_arm(snapshot.ppcMessage, snapshot.armMessage))')
old = '(state.armMessage && !(stmSubmitted >= 2 && state.armMessage == state.ppcMessage))'
replace(front, old, '(state.armMessage && !(stmSubmitted >= 2 && state.armMessage == state.ppcMessage) && !experiment_fs_prior_arm(state.ppcMessage, state.armMessage))', 3)
replace(front, '(stmSubmitted == 1 || stmSubmitted == 3 || stmSubmitted == 5)',
    '(stmSubmitted == 1 || stmSubmitted == 3 || stmSubmitted == 5 || stmSubmitted == 7)', 2)
replace(front, '(stmSubmitted >= 3 && ipc.armMessage == ipc.ppcMessage)',
    '((stmSubmitted >= 3 && ipc.armMessage == ipc.ppcMessage) || experiment_fs_prior_arm(ipc.ppcMessage, ipc.armMessage))')
replace(front, 'const bool cleared = ipc.armMessage == ipc.ppcMessage &&',
    'const bool cleared = (ipc.armMessage == ipc.ppcMessage || experiment_fs_prior_arm(ipc.ppcMessage, ipc.armMessage)) &&')
replace(output / 'si_external_delivery.h',
    'ipc.armMessage != ((ipc.ppcControl == 0x34 || stmSubmitted >= 3) ? ipc.ppcMessage : 0)',
    '(ipc.armMessage != ((ipc.ppcControl == 0x34 || stmSubmitted >= 3) ? ipc.ppcMessage : 0) && !(ipc.ppcControl == 0x32 && experiment_fs_prior_arm(ipc.ppcMessage, ipc.armMessage)))')
replace(output / 'si_external_delivery.h', 'extern unsigned stmSubmitted;',
    'extern unsigned stmSubmitted;\ninline bool experiment_fs_prior_arm(uint32_t message, uint32_t arm);')
replace(front, '(stmSubmitted == 4 && !std::getenv("SHSM_STM_ASYNC_DISABLED")))',
    '(stmSubmitted == 4 && !std::getenv("SHSM_STM_ASYNC_DISABLED")) || (stmSubmitted == 6 && !std::getenv("SHSM_FS_OPEN_DISABLED")))')
replace(front, '(!state.ppcMessage || (stmSubmitted >= 2 && state.ppcMessage == value))',
    '(!state.ppcMessage || (stmSubmitted >= 2 && state.ppcMessage == value) || (stmSubmitted == 6 && state.ppcMessage == 0x135e0020 && value == 0x135e0080))')
replace(front, '            if (stmSubmitted == 4) {', '''            if (stmSubmitted == 6) {
                const auto* packet = context.mmu.get_ptr(value);
                const std::array<uint32_t, 8> expected{1, 0, 0, 0x135e1000, 0, 0, 0, 0};
                if (value != 0x135e0080 || !devices::experiment_stm_pending()) {
                    throw std::runtime_error("FS OPEN packet/pending owner unverified");
                }
                for (unsigned index = 0; index < expected.size(); ++index) {
                    if (experiment_ipc_be32(packet + index * 4) != expected[index]) {
                        throw std::runtime_error("FS OPEN header unverified");
                    }
                }
                const std::array<uint8_t, 8> path{'/', 'd', 'e', 'v', '/', 'f', 's', 0};
                for (unsigned index = 0; index < path.size(); ++index) {
                    if (*experiment_ipc_mem1_span(context, 0x135e1000 + index, 1) != path[index]) {
                        throw std::runtime_error("FS OPEN path unverified");
                    }
                }
            }
            if (stmSubmitted == 4) {''')
fs_source = runtime / 'src/hle/devices/fs_device.cpp'
text = fs_source.read_text()
start = text.index('        vnand_init();', text.index('    int32_t open('))
end = text.index('    int32_t close(', start)
text = text[:start] + '''        if (path != "/dev/fs" || mode != 0) {
            throw std::runtime_error("FS device OPEN outside measured profile");
        }
        return IPC_OK;
    }

''' + text[end:]
text = '#include <stdexcept>\n' + text
(output / 'fs_device.cpp').write_text(text)
wrapper = output / 'boot-wrapper.cpp'
replace(wrapper, '    nwii::runtime::IOSKernel::get().register_device(nwii::runtime::devices::create_stm_device());',
    '    nwii::runtime::IOSKernel::get().register_device(nwii::runtime::devices::create_stm_device());\n    nwii::runtime::IOSKernel::get().register_device(nwii::runtime::devices::create_fs_device());')
replace(wrapper, '    original_trace_call(address, context);', '''    if (address == 0x80243570 && stmProduced == 3 && stmSubmitted == 8) {
        std::cout << "BOOT_FS_REPLY" << std::hex;
        for (uint32_t location : {0x80528b60u, 0x804b2b4cu, 0x935e0004u}) {
            std::cout << ' ' << bat_memory_read32(context, location);
        }
        std::cout << std::dec << '\\n';
        for (bool cached : {false, true}) {
            std::cout << (cached ? "BOOT_FS_CACHED" : "BOOT_FS_PHYSICAL");
            for (unsigned index = 0; index < 64; ++index) {
                std::cout << ' ' << unsigned(bat_memory_read8(context, 0x135e0080 + index +
                    (cached ? 0x80000000 : 0xc0000000)));
            }
            std::cout << '\\n';
        }
    }
    original_trace_call(address, context);''')
entry = output / 'mass_boot.cpp'
replace(entry, '        std::cout << "BOOT_REGISTERS";', '''        std::cout << "BOOT_FS_LAYOUT" << std::hex;
        for (uint32_t location : {0x80528b60u, 0x8052afa8u, 0x8052afacu, 0x8052afbcu}) {
            std::cout << ' ' << nwii::runtime::bat_memory_read32(context, location);
        }
        std::cout << std::dec << '\\n';
        std::cout << "BOOT_REGISTERS";''')
records = [dict(row) for row in build['records']]
includes = ['-include', str(output / 'finite_mem2_clear.h'), '-I', str(output), '-I', str(experiment),
    '-I', str(root / 'mass-current'), '-I', str(runtime / 'include')]
for name in ('output_62.cpp', 'output_67.cpp'):
    row = next(row for row in records if row['file'] == name)
    source = output / name
    source.write_bytes(Path(row['source']).read_bytes())
    obj = output / (name + '.o')
    result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-DSHSM_SI_EXTERNAL_DELIVERY',
        *includes, '-include', str(front), '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
    (output / (name + '.compile.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-3000:]
    row.update(source=str(source), sourceSha256=sha(source), object=str(obj), objectSha256=sha(obj))
sources = [wrapper, output / 'vi-clock-backend.cpp', output / 'processor_adapter.cpp', output / 'ai_mask_backend.cpp',
    output / 'dsp_startup_backend.cpp', runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp',
    runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/core/event_scheduler.cpp', root / 'stm-open-native/ios_kernel.cpp',
    output / 'stm_device.cpp', output / 'fs_device.cpp']
exe = output / 'openshsm-mass-boot'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit', *includes,
    '-include', str(output / 'interrupt_enable_observer.h'), '-DSHSM_SI_EXTERNAL_DELIVERY', '-DSHSM_PROCESSOR_ADAPTER',
    '-DSHSM_CACHE_ADAPTER', '-DSHSM_BOOT_INITIAL_MSR=0x30', '-I', str(runtime / 'src/hw'),
    '-I', str(runtime.parent / 'nWiiAnalyzer/include'), *map(str, sources), *[row['object'] for row in records],
    '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
(output / 'build.json').write_text(json.dumps({'builderSha256': sha(Path(__file__)), 'baseBuildSha256': sha(base / 'build.json'),
    'records': records, 'sourceHashes': {str(path): sha(path) for path in sources + [output / 'mass_boot.cpp', output / 'ipc_event_order_probe.cpp']},
    'headerHashes': {str(path): sha(path) for path in output.glob('*.h')}, 'executableSha256': sha(exe),
    'vendorFsSha256': sha(fs_source), 'limits': ['Exactly fourth FS OPEN; private existing FS specialization avoids synthetic VNand initialization.',
        'Shared registry/event/parser/STM owner retained; other FS commands, physical timing and first screen unverified.']}, indent=2) + '\n')
for mode in ('live', 'disabled'):
    env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
    if mode == 'disabled':
        env['SHSM_FS_OPEN_DISABLED'] = '1'
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(output / 'boot-quarantine.tsv'),
        str(root / 'sram-native/settings.bin')], env=env, capture_output=True, text=True, timeout=30)
    (output / (mode + '-boot.log')).write_text(result.stdout + result.stderr)
    print(mode + ': ' + '\n'.join(line for line in result.stdout.splitlines() if line.startswith(('BOOT_BOUNDARY', 'BOOT_FS_REPLY', 'BOOT_STM_ASYNC dispatched=', 'BOOT_STM submitted='))))

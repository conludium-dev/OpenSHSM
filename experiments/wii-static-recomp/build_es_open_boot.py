"""Admit the measured fifth ES OPEN on the existing private FS startup profile."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/build_fs_open_boot.py')
body = parent.read_text()
body = body.replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-fs-open-boot'")
body = body.replace("output = root / 'mass-fs-open-boot'", "output = root / 'mass-es-open-boot'")
body = body.replace("('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_fs_open_boot.py', 'verify_es_pending_dolphin.py')")
body = body.replace("'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'boot-quarantine.tsv'")
start = body.index("packet = output / 'ipc_open_packet.h'")
end = body.index('records = [dict(row)', start)
changes = r'''packet = output / 'ipc_open_packet.h'
replace(packet, 'path != "/dev/fs")', 'path != "/dev/fs" && path != "/dev/es")')
replace(packet, 'path == "/dev/fs")', 'path == "/dev/fs" || path == "/dev/es")')
front = output / 'ipc_ack_frontend.h'
replace(front, '(stmSubmitted == 1 || stmSubmitted == 3 || stmSubmitted == 5 || stmSubmitted == 7)',
    '(stmSubmitted == 1 || stmSubmitted == 3 || stmSubmitted == 5 || stmSubmitted == 7 || stmSubmitted == 9)', 2)
replace(front, '(stmSubmitted == 6 && !std::getenv("SHSM_FS_OPEN_DISABLED")))',
    '(stmSubmitted == 6 && !std::getenv("SHSM_FS_OPEN_DISABLED")) || (stmSubmitted == 8 && !std::getenv("SHSM_ES_OPEN_DISABLED")))')
replace(front, '            if (stmSubmitted == 4) {', ''' + repr('''            if (stmSubmitted == 8) {
                const auto* packet = context.mmu.get_ptr(value);
                const std::array<uint32_t, 8> expected{1, 2, 0, 0x528cf0, 0, 0, 0, 0};
                if (value != 0x135e0080 || !devices::experiment_stm_pending()) {
                    throw std::runtime_error("ES OPEN packet/pending owner unverified");
                }
                for (unsigned index = 0; index < expected.size(); ++index) {
                    if (experiment_ipc_be32(packet + index * 4) != expected[index]) {
                        throw std::runtime_error("ES OPEN header unverified");
                    }
                }
                const std::array<uint8_t, 8> path{'/', 'd', 'e', 'v', '/', 'e', 's', 0};
                for (unsigned index = 0; index < path.size(); ++index) {
                    if (*experiment_ipc_mem1_span(context, 0x528cf0 + index, 1) != path[index]) {
                        throw std::runtime_error("ES OPEN path unverified");
                    }
                }
            }
            if (stmSubmitted == 4) {''') + r''')
fs_source = runtime / 'src/hle/devices/es_device.cpp'
text = fs_source.read_text()
text = '#include <stdexcept>
' + text[:text.index('    int32_t ioctl(')] + ''' + repr('''    int32_t open(CPUContext&, const std::string& path, uint32_t mode) override {
        if (path != "/dev/es" || mode != 0) {
            throw std::runtime_error("ES OPEN outside measured profile");
        }
        return IPC_OK;
    }
    int32_t ioctl(CPUContext&, const IpcRequest&) override {
        throw std::runtime_error("ES IOCTL unverified");
    }
    int32_t ioctlv(CPUContext&, const IpcRequest&) override {
        throw std::runtime_error("ES IOCTLV unverified");
    }
};
std::unique_ptr<IDevice> create_es_device() {
    return std::make_unique<ESDevice>();
}
}
''') + r'''
(output / 'es_device.cpp').write_text(text)
wrapper = output / 'boot-wrapper.cpp'
replace(wrapper, '    nwii::runtime::IOSKernel::get().register_device(nwii::runtime::devices::create_fs_device());',
    '    nwii::runtime::IOSKernel::get().register_device(nwii::runtime::devices::create_fs_device());
    nwii::runtime::IOSKernel::get().register_device(nwii::runtime::devices::create_es_device());')
replace(wrapper, 'inline unsigned stmProduced = 0;', 'inline unsigned stmProduced = 0;
inline bool experimentEsCaptured = false;')
replace(wrapper, '    original_trace_call(address, context);', ''' + repr('''    if (!experimentEsCaptured && stmProduced == 4 && stmSubmitted == 10 && (context.msr & 0x10) &&
        bat_memory_read32(context, 0x80528ce8) == 3) {
        experimentEsCaptured = true;
        std::cout << "BOOT_ES_REPLY" << std::hex;
        for (uint32_t location : {0x80528ce8u, 0x804b2b4cu, 0x935e0004u}) {
            std::cout << ' ' << bat_memory_read32(context, location);
        }
        std::cout << std::dec << '\\n';
        for (bool cached : {false, true}) {
            std::cout << (cached ? "BOOT_ES_CACHED" : "BOOT_ES_PHYSICAL");
            for (unsigned index = 0; index < 64; ++index) {
                std::cout << ' ' << unsigned(bat_memory_read8(context, 0x135e0080 + index +
                    (cached ? 0x80000000 : 0xc0000000)));
            }
            std::cout << '\\n';
        }
    }
    original_trace_call(address, context);''') + r''')
entry = output / 'mass_boot.cpp'
replace(entry, '        std::cout << "BOOT_REGISTERS";', ''' + repr('''        if (context.pc == 0x80212ff4 && context.lr == 0x80242fc8 && context.msr == 0xa032 && context.gpr[29] == 0x935e0080) {
            for (bool cached : {false, true}) {
                std::cout << (cached ? "BOOT_ES_NEXT_CACHED" : "BOOT_ES_NEXT_PHYSICAL");
                for (unsigned index = 0; index < 64; ++index) {
                    std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context, 0x135e0080 + index +
                        (cached ? 0x80000000 : 0xc0000000)));
                }
                std::cout << '\\n';
            }
        }
        std::cout << "BOOT_REGISTERS";''') + r''')
replace(entry, '        std::cout << "BOOT_REGISTERS";', ''' + repr('''        std::cout << "BOOT_ES_LAYOUT " << std::hex << nwii::runtime::bat_memory_read32(context, 0x80528ce8) << std::dec << '\\n';
        std::cout << "BOOT_REGISTERS";''') + r''')
'''
# The replacement program uses Python literals, not generated C++ literals.
changes = changes.replace("'#include <stdexcept>\n'", repr('#include <stdexcept>\n'))
changes = changes.replace("'    nwii::runtime::IOSKernel::get().register_device(nwii::runtime::devices::create_fs_device());\n    nwii::runtime::IOSKernel::get().register_device(nwii::runtime::devices::create_es_device());'",
    repr('    nwii::runtime::IOSKernel::get().register_device(nwii::runtime::devices::create_fs_device());\n    nwii::runtime::IOSKernel::get().register_device(nwii::runtime::devices::create_es_device());'))
changes = changes.replace("'inline unsigned stmProduced = 0;\ninline bool experimentEsCaptured = false;'", repr('inline unsigned stmProduced = 0;\ninline bool experimentEsCaptured = false;'))
body = body[:start] + changes + body[end:]
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp'")
# Only the final run control changes; the retained FS admission flag stays independent.
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_ES_OPEN_DISABLED'] = '1'")
body = body.replace("'BOOT_FS_REPLY', 'BOOT_STM_ASYNC", "'BOOT_FS_REPLY', 'BOOT_ES_REPLY', 'BOOT_STM_ASYNC")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
import hashlib
import json
output = Path('work/private-game/static-recomp/mass-es-open-boot')
report = json.loads((output / 'build.json').read_text())
report['parentBuilderSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['vendorEsSha256'] = report.pop('vendorFsSha256')
report['limits'] = ['Exactly fifth ES OPEN; existing device specialization rejects all ES IOCTL/IOCTLV without zeroing outputs or returning synthetic title/ticket/certificate data.',
    'Shared registry/event/parser/STM owner and existing FS profile retained; native timing/loader remain PC adaptations.']
(output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')

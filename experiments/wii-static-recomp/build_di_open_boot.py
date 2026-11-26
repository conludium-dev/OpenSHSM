"""Admit only measured first DI OPEN through existing device, kernel and event mechanisms."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-sysconf-complete-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-di-open-boot'").replace(
    "('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('verify_di_events_dolphin.py',)").replace(
    "'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'boot-quarantine.tsv'")
start = body.index("packet = output / 'ipc_open_packet.h'")
end = body.index('records = [dict(row)', start)
changes = "front = output / 'ipc_ack_frontend.h'\nwrapper = output / 'boot-wrapper.cpp'\npacket = output / 'ipc_open_packet.h'\nfs_source = runtime / 'src/hle/devices/fs_device.cpp'\n"
changes += "replace(packet, '    if (length == 1 && physical >= 0x135e1180', '    if (length == 1 && physical >= 0x135e25c0 && physical < 0x135e25c8) { return context.mmu.get_ptr(physical); }\\n    if (length == 1 && physical >= 0x135e1180')\n"
changes += "replace(packet, 'path != \"/dev/es\" &&', 'path != \"/dev/es\" && path != \"/dev/di\" &&')\nreplace(packet, 'path == \"/dev/es\")', 'path == \"/dev/es\" || path == \"/dev/di\")')\n"
changes += "replace(front, '    if ((stmSubmitted == 25', '    if ((stmSubmitted == 29 || stmSubmitted == 30) && message == 0x135e0080 && arm == 0x135e00e0 && devices::experiment_stm_pending()) { return true; }\\n    if ((stmSubmitted == 25')\n"
odd = '(stmSubmitted == 1 || stmSubmitted == 3 || stmSubmitted == 5 || stmSubmitted == 7 || stmSubmitted == 9 || stmSubmitted == 11 || stmSubmitted == 13 || stmSubmitted == 15 || stmSubmitted == 17 || stmSubmitted == 19 || stmSubmitted == 21 || stmSubmitted == 23 || stmSubmitted == 25 || stmSubmitted == 27)'
changes += 'replace(front, ' + repr(odd) + ', ' + repr(odd[:-1] + ' || stmSubmitted == 29)') + ', 2)\n'
even = '(stmSubmitted == 20 || stmSubmitted == 22 || stmSubmitted == 24 || stmSubmitted == 26 || stmSubmitted == 28)'
changes += 'replace(front, ' + repr(even) + ', ' + repr(even[:-1] + ' || stmSubmitted == 30)') + ', 3)\n'
changes += "replace(output / 'si_external_delivery.h', '|| stmSubmitted == 28)', '|| stmSubmitted == 28 || stmSubmitted == 30)', 2)\n"
changes += "replace(front, '!std::getenv(\"SHSM_SC_PRODUCT_TAIL_DISABLED\")))', '!std::getenv(\"SHSM_SC_PRODUCT_TAIL_DISABLED\")) || (stmSubmitted == 28 && !std::getenv(\"SHSM_DI_OPEN_DISABLED\")))')\n"
changes += "replace(front, '(stmSubmitted == 26 && state.ppcMessage == 0x135e0080 && value == 0x135e00e0))', '(stmSubmitted == 26 && state.ppcMessage == 0x135e0080 && value == 0x135e00e0) || (stmSubmitted == 28 && state.ppcMessage == 0x135e00e0 && value == 0x135e0080))')\n"
guard = '''            if (stmSubmitted == 28) {
                const std::array<uint32_t, 8> expected{1, 0x100, 0, 0x135e25c0, 0, 1, 0x80540010, 0};
                if (value != 0x135e0080 || context.msr != 0x2032 || !devices::experiment_stm_pending()) {
                    throw std::runtime_error("DI OPEN address/MSR/owner unverified");
                }
                for (unsigned index = 0; index < expected.size(); ++index) {
                    if (experiment_ipc_be32(context.mmu.get_ptr(value) + index * 4) != expected[index]) {
                        throw std::runtime_error("DI OPEN header unverified");
                    }
                }
                for (unsigned index = 32; index < 64; ++index) {
                    if (experiment_ipc_mem1_span(context, value, 64)[index]) {
                        throw std::runtime_error("DI OPEN packet tail unverified");
                    }
                }
                const std::array<uint8_t, 8> path{'/', 'd', 'e', 'v', '/', 'd', 'i', 0};
                for (unsigned index = 0; index < path.size(); ++index) {
                    if (*experiment_ipc_mem1_span(context, 0x135e25c0 + index, 1) != path[index]) {
                        throw std::runtime_error("DI OPEN path unverified");
                    }
                }
            }
'''
changes += "replace(front, '            if (stmSubmitted == 24 ||', " + repr(guard + '            if (stmSubmitted == 24 ||') + ")\n"
changes += "replace(wrapper, '    if (stmSubmitted == 17) {', '    if (stmSubmitted == 17 || stmSubmitted == 29) {')\n"
changes += "replace(wrapper, '    nwii::runtime::IOSKernel::get().register_device(nwii::runtime::devices::create_es_device());', '    nwii::runtime::IOSKernel::get().register_device(nwii::runtime::devices::create_es_device());\\n    nwii::runtime::IOSKernel::get().register_device(nwii::runtime::devices::create_di_device());')\n"
di_methods = '''    int32_t open(CPUContext&, const std::string& path, uint32_t mode) override {
        if (path != "/dev/di" || mode != 0) {
            throw std::runtime_error("DI OPEN outside verified profile");
        }
        return IPC_OK;
    }
    int32_t close(CPUContext&, uint32_t) override { throw std::runtime_error("DI CLOSE unverified"); }
    int32_t read(CPUContext&, uint32_t, uint32_t, uint32_t) override { throw std::runtime_error("DI READ unverified"); }
    int32_t write(CPUContext&, uint32_t, uint32_t, uint32_t) override { throw std::runtime_error("DI WRITE unverified"); }
    int32_t seek(CPUContext&, uint32_t, int32_t, int32_t) override { throw std::runtime_error("DI SEEK unverified"); }
    int32_t ioctl(CPUContext&, const IpcRequest&) override { throw std::runtime_error("DI IOCTL unverified"); }
    int32_t ioctlv(CPUContext&, const IpcRequest&) override { throw std::runtime_error("DI IOCTLV unverified"); }
'''
changes += "di_source = runtime / 'src/hle/devices/di_device.cpp'\ndi = di_source.read_text()\nclass_start = di.index('class DIDevice')\nmethod_start = di.index('    int32_t ioctl(', class_start)\nclass_end = di.index('\\n};', method_start)\n(output / 'di_device.cpp').write_text('#include \"runtime/devices.h\"\\n#include <stdexcept>\\nnamespace nwii::runtime::devices {\\n' + di[class_start:method_start] + " + repr(di_methods) + " + di[class_end:])\n"
observer = '''inline void experiment_di_return_observe(CPUContext& context) {
    if (stmSubmitted == 30) {
        std::cout << "DI_ORIGINAL_RETURN" << std::hex << ' ' << context.gpr[3] << ' ' << context.msr;
        for (uint32_t address : {0x80528a98u, 0x8052ac90u, 0x8052ac94u, 0x8052afc4u, 0x804b2b4cu, 0x935e0004u,
            0x804b2a80u, 0x804b2a84u}) {
            std::cout << ' ' << bat_memory_read32(context, address);
        }
        std::cout << std::dec << '\\n';
        for (bool cached : {false, true}) {
            std::cout << (cached ? "DI_REPLY_CACHED" : "DI_REPLY_PHYSICAL");
            for (unsigned index = 0; index < 64; ++index) {
                std::cout << ' ' << unsigned(bat_memory_read8(context, (cached ? 0x935e0080u : 0xd35e0080u) + index));
            }
            std::cout << '\\n';
        }
    }
}
'''
changes += "replace(front, 'inline unsigned stmSubmitted = 0;', " + repr('inline unsigned stmSubmitted = 0;\n' + observer) + ")\n"
body = body[:start] + changes + body[end:]
body = body.replace("('output_62.cpp', 'output_67.cpp')", "('output_62.cpp', 'output_65.cpp', 'output_67.cpp')")
body = body.replace("    source.write_bytes(Path(row['source']).read_bytes())", "    source.write_bytes(Path(row['source']).read_bytes())\n    if name == 'output_65.cpp':\n        replace(source, 'loc_80225CBC: ;', 'loc_80225CBC: ;\\n    nwii::runtime::experiment_di_return_observe(ctx);')")
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp', output / 'di_device.cpp'")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_DI_OPEN_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'\n    env['SHSM_SC_LAB_FILE'] = '_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF'\n    env['SHSM_SC_LAB_PRODUCT'] = '_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt'\n    result = subprocess.run([str(exe),")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-di-open-boot')
report = json.loads((output / 'build.json').read_text())
report['parentBuilderSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['vendorDiSha256'] = hashlib.sha256(Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime/src/hle/devices/di_device.cpp').read_bytes()).hexdigest()
report['limits'] = ['First DI OPEN only through existing class/factory/shared kernel/events; all other DI commands refuse.',
    'Source SDK return requires verification; ignored pointer relocation and event timing are PC adaptations, not physical cycles.']
(output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')

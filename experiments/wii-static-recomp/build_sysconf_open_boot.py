"""Integrate first async file OPEN against explicit private laboratory console data."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-sysconf-path-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-sysconf-open-boot'")
body = body.replace("('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_sysconf_path_boot.py', 'verify_sysconf_events.py')")
body = body.replace("'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'boot-quarantine.tsv'")
start = body.index("packet = output / 'ipc_open_packet.h'")
end = body.index('records = [dict(row)', start)
changes = '''front = output / 'ipc_ack_frontend.h'
wrapper = output / 'boot-wrapper.cpp'
packet = output / 'ipc_open_packet.h'
replace(packet, '    if (length == 1 && physical >= 0x135e1000',
    '    if (length == 1 && physical >= 0x135e1020 && physical < 0x135e1035) { return context.mmu.get_ptr(physical); }\\n    if (length == 1 && physical >= 0x135e1000')
replace(packet, 'path.rfind("/dev/", 0) != 0)', 'path.rfind("/dev/", 0) != 0 && path != "/shared2/sys/SYSCONF")')
replace(packet, 'path != "/dev/es") ||', 'path != "/dev/es" && path != "/shared2/sys/SYSCONF") ||')
replace(packet, '    const auto result = IOSKernel::get().open(context, path, mode);',
    '    if (path == "/shared2/sys/SYSCONF" && mode != 1) { throw std::runtime_error("SYSCONF OPEN mode unverified"); }\\n    const auto result = IOSKernel::get().open(context, path, mode);')
replace(front, '|| stmSubmitted == 15)', '|| stmSubmitted == 15 || stmSubmitted == 17)', 2)
replace(front, '(stmSubmitted == 14 && !std::getenv("SHSM_ES_CLOSE_DISABLED")))',
    '(stmSubmitted == 14 && !std::getenv("SHSM_ES_CLOSE_DISABLED")) || (stmSubmitted == 16 && !std::getenv("SHSM_SYSCONF_OPEN_DISABLED")))')
'''
guard = '''            if (stmSubmitted == 16) {
                const std::array<uint32_t, 8> expected{1, 0, 0, 0x135e1020, 1, 1, 0x80540010, 0};
                if (value != 0x135e0080 || !devices::experiment_stm_pending()) {
                    throw std::runtime_error("SYSCONF OPEN address/pending owner unverified");
                }
                for (unsigned index = 0; index < expected.size(); ++index) {
                    if (experiment_ipc_be32(context.mmu.get_ptr(value) + index * 4) != expected[index]) {
                        throw std::runtime_error("SYSCONF OPEN physical header unverified");
                    }
                }
                if (bat_memory_read32(context, 0x935e00a0) != 0x80240680 ||
                    bat_memory_read32(context, 0x935e00a4) != 0x935e1020) {
                    throw std::runtime_error("SYSCONF OPEN cached callback unverified");
                }
            }
'''
changes += "replace(front, '            if (stmSubmitted == 14) {', " + repr(guard + '            if (stmSubmitted == 14) {') + ")\n"
fs_open = '''        if (path == "/dev/fs" && mode == 0) {
            return IPC_OK;
        }
        if (path != "/shared2/sys/SYSCONF" || mode != 1 || m_sysconf.is_open()) {
            throw std::runtime_error("FS device OPEN outside measured read-only laboratory profile");
        }
        const auto* source = std::getenv("SHSM_SC_LAB_FILE");
        if (!source || !*source) {
            throw std::runtime_error("Explicit laboratory console configuration required");
        }
        m_sysconf.open(source, std::ios::binary);
        if (!m_sysconf || m_sysconf.seekg(0, std::ios::end).tellg() != 0x4000) {
            m_sysconf.close();
            throw std::runtime_error("Laboratory SYSCONF file unavailable or wrong length");
        }
        m_sysconf.seekg(0);
        std::array<char, 4> head{}, tail{};
        m_sysconf.read(head.data(), 4);
        m_sysconf.seekg(0x3ffc);
        m_sysconf.read(tail.data(), 4);
        if (!m_sysconf || head != std::array<char, 4>{'S', 'C', 'v', '0'} ||
            tail != std::array<char, 4>{'S', 'C', 'e', 'd'}) {
            m_sysconf.close();
            throw std::runtime_error("Laboratory SYSCONF framing unverified");
        }
        m_sysconf.seekg(0);
        return 20;
'''
old_open = '''        if (path != "/dev/fs" || mode != 0) {
            throw std::runtime_error("FS device OPEN outside measured profile");
        }
        return IPC_OK;
'''
changes += "fs_source = runtime / 'src/hle/devices/fs_device.cpp'\nfs = output / 'fs_device.cpp'\n"
changes += "replace(fs, '#include <stdexcept>', '#include <stdexcept>\\n#include <fstream>\\n#include <array>\\n#include <cstdlib>')\n"
changes += "replace(fs, 'class FSDevice : public IDevice {', 'class FSDevice : public IDevice {\\n    std::ifstream m_sysconf;')\n"
changes += "replace(fs, " + repr(old_open) + ", " + repr(fs_open) + ")\n"
changes += "replace(fs, '        int slot = fd - VNAND_FD_BASE;', '        if (fd == 20) { throw std::runtime_error(\"Laboratory file operation not yet verified\"); }\\n        int slot = fd - VNAND_FD_BASE;', 4)\n"
observe = '''    if (stmSubmitted == 18 && (address == 0x80240680 || address == 0x80244e30 || address == 0x80247730)) {
        std::cout << "SC_OPEN_CALLBACK" << std::hex << ' ' << address << ' ' << context.msr << ' '
            << context.gpr[3] << ' ' << context.gpr[4] << ' ' << bat_memory_read32(context, 0x804b2b4c)
            << std::dec << '\\n';
        for (bool cached : {false, true}) {
            std::cout << (cached ? "SC_OPEN_REPLY_CACHED" : "SC_OPEN_REPLY_PHYSICAL") << std::hex << ' ' << address << std::dec;
            for (unsigned index = 0; index < 64; ++index) {
                std::cout << ' ' << unsigned(bat_memory_read8(context, (cached ? 0x935e0080u : 0xd35e0080u) + index));
            }
            std::cout << '\\n';
        }
    }
'''
changes += "replace(wrapper, '    original_trace_call(address, context);', " + repr(observe + '    original_trace_call(address, context);') + ")\n"
return_observer = '''inline void experiment_sysconf_return_observe(CPUContext& context) {
    if (stmSubmitted == 18) {
        std::cout << "SC_OPEN_API_RETURN" << std::hex << ' ' << context.gpr[3] << ' ' << context.msr
            << ' ' << bat_memory_read32(context, 0x935e0080) << ' ' << hw::experiment_ipc_snapshot().ppcControl << std::dec << '\\n';
    }
}
'''
changes += "replace(front, 'inline unsigned stmSubmitted = 0;', " + repr('inline unsigned stmSubmitted = 0;\n' + return_observer) + ")\n"
async_delivery = '''    if (stmSubmitted == 17) {
        hw::ipc_ppc_ctrl = 0x31;
        EventScheduler::get().schedule_after(64, [](CPUContext&, uint64_t) {
            hw::ipc_ppc_ctrl = (hw::ipc_ppc_ctrl & ~1u) | 2;
        });
        hw::experiment_fixture_reply_after(request, 65, [request](CPUContext& active, uint64_t) {
            experiment_ipc_open_packet(active, request);
            ++stmProduced;
            experimentStmIrq = true;
        });
        return;
    }
'''
changes += "replace(wrapper, 'void experiment_stm_submit(CPUContext&, uint32_t request) {', " + repr('void experiment_stm_submit(CPUContext&, uint32_t request) {\n' + async_delivery) + ")\n"
changes += "replace(output / 'mass_boot.cpp', 'nwii::runtime::stmSubmitted == 16)', 'nwii::runtime::stmSubmitted == 16 || nwii::runtime::stmSubmitted == 18)')\n"
final_observer = '''        if (nwii::runtime::stmSubmitted == 18) {
            std::cout << "SC_NESTED_READ_CACHED";
            for (unsigned index = 0; index < 64; ++index) {
                std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context, 0x935e00e0 + index));
            }
            std::cout << '\\n' << "SC_OPEN_FILEINFO" << std::hex << ' '
                << nwii::runtime::bat_memory_read32(context, 0x804b3008) << ' '
                << nwii::runtime::bat_memory_read32(context, 0x804b2b4c) << ' '
                << nwii::runtime::bat_memory_read32(context, 0x935e1280) << ' '
                << nwii::runtime::bat_memory_read32(context, 0x935e1284) << std::dec << '\\n';
        }
'''
changes += "replace(output / 'mass_boot.cpp', '        std::cout << \"BOOT_ES_LAYOUT \"', " + repr(final_observer + '        std::cout << "BOOT_ES_LAYOUT "') + ")\n"
body = body[:start] + changes + body[end:]
body = body.replace("('output_62.cpp', 'output_67.cpp')", "('output_62.cpp', 'output_63.cpp', 'output_67.cpp')")
body = body.replace("    source.write_bytes(Path(row['source']).read_bytes())", "    source.write_bytes(Path(row['source']).read_bytes())\n    if name == 'output_67.cpp':\n        replace(source, 'loc_80242530: ;', 'loc_80242530: ;\\n    nwii::runtime::experiment_sysconf_return_observe(ctx);')")
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp'")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_SYSCONF_OPEN_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'\n    env['SHSM_SC_LAB_FILE'] = '_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF'\n    result = subprocess.run([str(exe),")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-sysconf-open-boot')
report = json.loads((output / 'build.json').read_text())
report['parentBuilderSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['laboratoryConsoleFileSha256'] = hashlib.sha256(Path('_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF').read_bytes()).hexdigest()
report['limits'] = ['First async read-only OPEN through existing kernel/FS device against an explicit private laboratory file.',
    'Internal handle20 is a PC adapter; external descriptor allocated by unchanged shared kernel. Native READ/CLOSE and production console-settings policy unverified.']
(output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')

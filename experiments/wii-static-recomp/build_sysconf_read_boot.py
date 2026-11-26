"""Execute measured nested READ through existing cache/IPC/kernel/FS mechanisms."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-sysconf-open-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-sysconf-read-boot'")
body = body.replace("('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_sysconf_open_boot.py', 'verify_sysconf_events.py')")
body = body.replace("'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'boot-quarantine.tsv'")
start = body.index("packet = output / 'ipc_open_packet.h'")
end = body.index('records = [dict(row)', start)
changes = "front = output / 'ipc_ack_frontend.h'\nwrapper = output / 'boot-wrapper.cpp'\nflush = output / 'flush_syscall.h'\nfs_source = runtime / 'src/hle/devices/fs_device.cpp'\n"
changes += "replace(flush, 'inline bool experimentFlushPacket = false;', 'inline bool experimentFlushPacket = false;\\ninline bool experimentFlushCallback = false;')\n"
gate = '''    bool nestedRead = !std::getenv("SHSM_SYSCONF_READ_DISABLED") && context.msr == 0x32 &&
        stmSubmitted == 18 && context.lr == 0x80242240 && context.gpr[3] == 0x935e0100 && context.gpr[4] == 1 &&
        devices::experiment_stm_pending();
    const std::array<uint32_t, 10> expected{3, 0, 3, 0x4b31a0, 0x4000, 0, 0, 0, 0x80240680, 0x935e1180};
    for (unsigned index = 0; index < expected.size() && nestedRead; ++index) {
        nestedRead &= bat_memory_read32(context, 0x935e00e0 + index * 4) == expected[index];
    }
    nestedRead &= !nestedRead || (bat_memory_read32(context, 0x804b3008) == 3 &&
        bat_memory_read32(context, 0x804b2b4c) == 0x935e0120 &&
        bat_memory_read32(context, 0x935e1280) == 0x802464b0 &&
        bat_memory_read32(context, 0x935e1284) == 0x804b3094);
'''
changes += "replace(flush, '    bool sysconfPathFlush = false;', " + repr(gate + '    bool sysconfPathFlush = false;') + ")\n"
changes += "replace(flush, '(context.msr != 0x2032 && context.msr != 0xa032)', '(context.msr != 0x2032 && context.msr != 0xa032 && !nestedRead)')\n"
changes += "replace(flush, '    context.srr0 = instruction + 4;', '    experimentFlushCallback = nestedRead;\\n    context.srr0 = instruction + 4;')\n"
changes += "replace(flush, 'context.msr != 0x2000', 'context.msr != (experimentFlushCallback ? 0u : 0x2000u)', 3)\n"
changes += "replace(flush, '(context.srr1 != 0x2032 && (!experimentFlushEe || context.srr1 != 0xa032))', '(context.srr1 != 0x2032 && (!experimentFlushEe || context.srr1 != 0xa032) && !(experimentFlushCallback && context.srr1 == 0x32))')\n"
changes += "replace(flush, '    state.flushPhase = 0;', '    experimentFlushCallback = false;\\n    state.flushPhase = 0;')\n"
changes += "replace(front, '    return (stmSubmitted == 7 || stmSubmitted == 8)', '    if ((stmSubmitted == 19 || stmSubmitted == 20) && message == 0x135e00e0 && arm == 0x135e0080 && devices::experiment_stm_pending()) { return true; }\\n    return (stmSubmitted == 7 || stmSubmitted == 8)')\n"
changes += "replace(front, 'experimentStmIrq && context.msr == 0x2032 && (stmSubmitted', 'experimentStmIrq && (context.msr == 0x2032 || (context.msr == 0x32 && stmSubmitted == 19)) && (stmSubmitted')\n"
changes += "replace(front, 'context.pc == 0x80241c30 && context.msr == 0x2032 &&', 'context.pc == 0x80241c30 && (context.msr == 0x2032 || (context.msr == 0x32 && (stmSubmitted == 18 || stmSubmitted == 19))) &&')\n"
changes += "replace(front, '|| stmSubmitted == 17)', '|| stmSubmitted == 17 || stmSubmitted == 19)', 2)\n"
changes += "replace(front, '(stmSubmitted == 16 && !std::getenv(\"SHSM_SYSCONF_OPEN_DISABLED\")))', '(stmSubmitted == 16 && !std::getenv(\"SHSM_SYSCONF_OPEN_DISABLED\")) || (stmSubmitted == 18 && !std::getenv(\"SHSM_SYSCONF_READ_DISABLED\")))')\n"
changes += "replace(front, '&& value == 0x135e0080)) &&', '&& value == 0x135e0080) || (stmSubmitted == 18 && state.ppcMessage == 0x135e0080 && value == 0x135e00e0)) &&')\n"
guard = '''            if (stmSubmitted == 18) {
                const std::array<uint32_t, 8> expected{3, 0, 3, 0x4b31a0, 0x4000, 0, 0, 0};
                if (context.msr != 0x32 || value != 0x135e00e0 || !devices::experiment_stm_pending()) {
                    throw std::runtime_error("Nested READ sender address/MSR/pending unverified");
                }
                for (unsigned index = 0; index < expected.size(); ++index) {
                    if (experiment_ipc_be32(context.mmu.get_ptr(value) + index * 4) != expected[index]) {
                        throw std::runtime_error("Nested READ physical header unverified");
                    }
                }
                if (bat_memory_read32(context, 0x935e0100) != 0x80240680 ||
                    bat_memory_read32(context, 0x935e0104) != 0x935e1180) {
                    throw std::runtime_error("Nested READ cached callback unverified");
                }
            }
'''
changes += "replace(front, '            if (stmSubmitted == 16) {', " + repr(guard + '            if (stmSubmitted == 16) {') + ")\n"
changes += "replace(front, 'context.msr != 0x2030 && !(', 'context.msr != 0x2030 && !(context.msr == 0x32 && stmSubmitted == 20) && !(')\n"
changes += "replace(front, 'ipc.ppcControl == 0x30 && value == 0x38 && ipc.armMessage == ipc.ppcMessage;', 'ipc.ppcControl == 0x30 && value == 0x38 && (ipc.armMessage == ipc.ppcMessage || experiment_fs_prior_arm(ipc.ppcMessage, ipc.armMessage));')\n"
changes += "replace(front, 'const bool ack = ipc.ppcControl == 0x32 &&', 'const bool ack = (ipc.ppcControl == 0x32 || (stmSubmitted == 20 && ipc.ppcControl == 0x3a)) &&')\n"
changes += "replace(front, 'context.lr == 0x80241f68 && ipc.ppcControl == 0x32 &&', 'context.lr == 0x80241f68 && (ipc.ppcControl == 0x32 || (stmSubmitted == 20 && ipc.ppcControl == 0x3a)) &&')\n"
changes += "si = output / 'si_external_delivery.h'\nreplace(si, '(ipc.ppcControl != 0x32 && ipc.ppcControl != 0x34)', '(ipc.ppcControl != 0x32 && ipc.ppcControl != 0x34 && !(stmSubmitted == 20 && ipc.ppcControl == 0x3a))')\n"
changes += "replace(si, '!(ipc.ppcControl == 0x32 && experiment_fs_prior_arm', '!((ipc.ppcControl == 0x32 || (stmSubmitted == 20 && ipc.ppcControl == 0x3a)) && experiment_fs_prior_arm')\n"
dispatch = '''    if (stmSubmitted == 19) {
        hw::ipc_ppc_ctrl = 0x30;
        EventScheduler::get().schedule_after(64, [](CPUContext&, uint64_t) {
            hw::ipc_ppc_ctrl = (hw::ipc_ppc_ctrl & ~1u) | 2;
        });
        hw::experiment_fixture_reply_after(request, 65, [request](CPUContext& active, uint64_t) {
            auto* packet = experiment_ipc_mem1_span(active, request, 64);
            const std::array<uint32_t, 8> expected{3, 0, 3, 0x4b31a0, 0x4000, 0, 0, 0};
            if (request != 0x135e00e0 || !devices::experiment_stm_pending()) {
                throw std::runtime_error("Nested READ producer owner/address unverified");
            }
            for (unsigned index = 0; index < expected.size(); ++index) {
                if (experiment_ipc_be32(packet + index * 4) != expected[index]) {
                    throw std::runtime_error("Nested READ producer header unverified");
                }
            }
            const auto result = IOSKernel::get().read(active, 3, 0x4b31a0, 0x4000);
            if (result != 0x4000) { throw std::runtime_error("Nested READ result outside measured profile"); }
            experiment_ipc_store_be32(packet, 8);
            experiment_ipc_store_be32(packet + 4, uint32_t(result));
            experiment_ipc_store_be32(packet + 8, 3);
            ++stmProduced;
        });
        return;
    }
'''
changes += "replace(wrapper, '    if (stmSubmitted == 17) {', " + repr(dispatch + '    if (stmSubmitted == 17) {') + ")\n"
observer = '''    if (stmSubmitted == 20 && address == 0x802438b0) {
        std::cout << "SC_READ_FREE" << std::hex << ' ' << context.gpr[3] << ' ' << context.gpr[4]
            << ' ' << context.msr << std::dec << '\\n';
    }
    if (stmSubmitted == 20 && (address == 0x80240680 || address == 0x80247800)) {
        std::cout << "SC_READ_CALLBACK" << std::hex << ' ' << address << ' ' << context.gpr[3] << ' '
            << context.gpr[4] << ' ' << context.msr << std::dec << '\\n';
        for (bool cached : {false, true}) {
            std::cout << (cached ? "SC_READ_REPLY_CACHED" : "SC_READ_REPLY_PHYSICAL") << std::hex << ' ' << address << std::dec;
            for (unsigned index = 0; index < 64; ++index) {
                std::cout << ' ' << unsigned(bat_memory_read8(context, (cached ? 0x935e00e0u : 0xd35e00e0u) + index));
            }
            std::cout << '\\n';
        }
    }
'''
changes += "replace(wrapper, '    original_trace_call(address, context);', " + repr(observer + '    original_trace_call(address, context);') + ")\n"
snapshot = '''        if (nwii::runtime::stmSubmitted == 20) {
            for (bool cached : {false, true}) {
                std::cout << (cached ? "SC_READ_BUFFER_CACHED" : "SC_READ_BUFFER_PHYSICAL");
                for (unsigned index = 0; index < 0x4000; ++index) {
                    std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context,
                        (cached ? 0x804b31a0u : 0xc04b31a0u) + index));
                }
                std::cout << '\\n';
            }
        }
'''
changes += "replace(output / 'mass_boot.cpp', '        std::cout << \"BOOT_ES_LAYOUT \"', " + repr(snapshot + '        std::cout << "BOOT_ES_LAYOUT "') + ")\n"
read = '''        if (fd == 20) {
            if (!m_sysconf.is_open() || buf != 0x4b31a0 || len != 0x4000 || m_sysconf.tellg() != 0) {
                throw std::runtime_error("Laboratory READ outside measured first-transfer profile");
            }
            auto* destination = ctx.mmu.get_ptr(buf);
            if (!destination || ctx.mmu.get_ptr(buf + len - 1) != destination + len - 1) {
                throw std::runtime_error("Laboratory READ backing unavailable");
            }
            std::array<char, 0x4000> data{};
            m_sysconf.read(data.data(), data.size());
            if (!m_sysconf || m_sysconf.gcount() != 0x4000) {
                throw std::runtime_error("Laboratory READ short input");
            }
            std::memcpy(destination, data.data(), data.size());
            return int32_t(m_sysconf.gcount());
        }
'''
changes += "fs = output / 'fs_device.cpp'\nfs_text = fs.read_text()\nread_start = fs_text.index('    int32_t read(')\nread_end = fs_text.index('    int32_t write(', read_start)\nold_read = fs_text[read_start:read_end]\nassert old_read.count('        if (fd == 20) { throw std::runtime_error(\"Laboratory file operation not yet verified\"); }') == 1\n"
changes += "new_read = old_read.replace('        if (fd == 20) { throw std::runtime_error(\"Laboratory file operation not yet verified\"); }', " + repr(read.rstrip()) + ")\nreplace(fs, old_read, new_read)\n"
body = body[:start] + changes + body[end:]
body = body.replace("('output_62.cpp', 'output_67.cpp')", "('output_62.cpp', 'output_63.cpp', 'output_67.cpp')")
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp'")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_SYSCONF_READ_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'\n    env['SHSM_SC_LAB_FILE'] = '_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF'\n    result = subprocess.run([str(exe),")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-sysconf-read-boot')
report = json.loads((output / 'build.json').read_text())
report['parentBuilderSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['laboratoryConsoleFileSha256'] = json.loads(Path('work/private-game/static-recomp/mass-sysconf-open-boot/build.json').read_text())['laboratoryConsoleFileSha256']
report['limits'] = ['Only exact nested READ under MSR32; original register state and allocation ownership retained.',
    'Immediate X1 request consumption and ACK64/reply65 are PC handshake/timing adaptations, not physical Wii cycle accuracy.',
    'Actual laboratory file bytes read through existing kernel/FSDevice. Subsequent CLOSE/SC completion and production settings policy unverified.']
(output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')

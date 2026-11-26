"""First actual async file CLOSE through the existing stream/kernel/IPC mechanisms."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-sysconf-read-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-sysconf-close-boot'")
body = body.replace("('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_sysconf_read_boot.py', 'verify_sysconf_close_prepared.py')")
body = body.replace("'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'boot-quarantine.tsv'")
start = body.index("packet = output / 'ipc_open_packet.h'")
end = body.index('records = [dict(row)', start)
changes = "front = output / 'ipc_ack_frontend.h'\nwrapper = output / 'boot-wrapper.cpp'\nflush = output / 'flush_syscall.h'\nfs_source = runtime / 'src/hle/devices/fs_device.cpp'\n"
gate = '''    bool nestedClose = !std::getenv("SHSM_SYSCONF_CLOSE_DISABLED") && context.msr == 0x32 &&
        stmSubmitted == 20 && context.lr == 0x80242240 && context.gpr[3] == 0x935e00a0 && context.gpr[4] == 1 &&
        devices::experiment_stm_pending();
    const std::array<uint32_t, 10> closeExpected{2, 3, 3, 0x135e1020, 1, 1, 0x80540010, 0, 0x80240680, 0x935e1020};
    for (unsigned index = 0; index < closeExpected.size() && nestedClose; ++index) {
        nestedClose &= bat_memory_read32(context, 0x935e0080 + index * 4) == closeExpected[index];
    }
    nestedClose &= !nestedClose || (bat_memory_read32(context, 0x935e1120) == 0x80245af0 &&
        bat_memory_read32(context, 0x935e1124) == 0x804b3094 &&
        bat_memory_read32(context, 0x804b3098) == 0x802478f0);
'''
changes += "replace(flush, '    bool sysconfPathFlush = false;', " + repr(gate + '    bool sysconfPathFlush = false;') + ")\n"
changes += "replace(flush, '&& !nestedRead)', '&& !nestedRead && !nestedClose)')\nreplace(flush, 'experimentFlushCallback = nestedRead;', 'experimentFlushCallback = nestedRead || nestedClose;')\n"
changes += "replace(front, '    if ((stmSubmitted == 19 || stmSubmitted == 20)', '    if ((stmSubmitted == 21 || stmSubmitted == 22) && message == 0x135e0080 && arm == 0x135e00e0 && devices::experiment_stm_pending()) { return true; }\\n    if ((stmSubmitted == 19 || stmSubmitted == 20)')\n"
changes += "replace(front, 'context.msr == 0x32 && stmSubmitted == 19', 'context.msr == 0x32 && (stmSubmitted == 19 || stmSubmitted == 21)')\n"
changes += "replace(front, '(stmSubmitted == 18 || stmSubmitted == 19)', '(stmSubmitted == 18 || stmSubmitted == 19 || stmSubmitted == 20 || stmSubmitted == 21)')\n"
changes += "replace(front, '|| stmSubmitted == 19)', '|| stmSubmitted == 19 || stmSubmitted == 21)', 2)\n"
changes += "replace(front, '(stmSubmitted == 18 && !std::getenv(\"SHSM_SYSCONF_READ_DISABLED\")))', '(stmSubmitted == 18 && !std::getenv(\"SHSM_SYSCONF_READ_DISABLED\")) || (stmSubmitted == 20 && !std::getenv(\"SHSM_SYSCONF_CLOSE_DISABLED\")))')\n"
changes += "replace(front, '&& value == 0x135e00e0)) &&', '&& value == 0x135e00e0) || (stmSubmitted == 20 && state.ppcMessage == 0x135e00e0 && value == 0x135e0080)) &&')\n"
changes += "replace(front, 'context.msr == 0x32 && stmSubmitted == 20', 'context.msr == 0x32 && (stmSubmitted == 20 || stmSubmitted == 22)')\n"
changes += "replace(front, 'stmSubmitted == 20 && ipc.ppcControl == 0x3a', '(stmSubmitted == 20 || stmSubmitted == 22) && ipc.ppcControl == 0x3a', 2)\n"
changes += "replace(output / 'si_external_delivery.h', 'stmSubmitted == 20 && ipc.ppcControl == 0x3a', '(stmSubmitted == 20 || stmSubmitted == 22) && ipc.ppcControl == 0x3a', 2)\n"
guard = '''            if (stmSubmitted == 20) {
                const std::array<uint32_t, 8> expected{2, 3, 3, 0x135e1020, 1, 1, 0x80540010, 0};
                if (context.msr != 0x32 || value != 0x135e0080 || !devices::experiment_stm_pending()) {
                    throw std::runtime_error("Nested CLOSE sender address/MSR/owner unverified");
                }
                for (unsigned index = 0; index < expected.size(); ++index) {
                    if (experiment_ipc_be32(context.mmu.get_ptr(value) + index * 4) != expected[index]) {
                        throw std::runtime_error("Nested CLOSE physical header unverified");
                    }
                }
            }
'''
changes += "replace(front, '            if (stmSubmitted == 18) {', " + repr(guard + '            if (stmSubmitted == 18) {') + ")\n"
dispatch = '''    if (stmSubmitted == 21) {
        hw::ipc_ppc_ctrl = 0x30;
        EventScheduler::get().schedule_after(64, [](CPUContext&, uint64_t) {
            hw::ipc_ppc_ctrl = (hw::ipc_ppc_ctrl & ~1u) | 2;
        });
        hw::experiment_fixture_reply_after(request, 65, [request](CPUContext& active, uint64_t) {
            auto* packet = experiment_ipc_mem1_span(active, request, 64);
            const std::array<uint32_t, 8> expected{2, 3, 3, 0x135e1020, 1, 1, 0x80540010, 0};
            if (request != 0x135e0080 || !devices::experiment_stm_pending()) {
                throw std::runtime_error("Nested CLOSE producer owner/address unverified");
            }
            for (unsigned index = 0; index < expected.size(); ++index) {
                if (experiment_ipc_be32(packet + index * 4) != expected[index]) {
                    throw std::runtime_error("Nested CLOSE producer header unverified");
                }
            }
            const auto result = IOSKernel::get().close(active, 3);
            if (result != IPC_OK) { throw std::runtime_error("Nested CLOSE result outside measured profile"); }
            experiment_ipc_store_be32(packet, 8);
            experiment_ipc_store_be32(packet + 4, uint32_t(result));
            experiment_ipc_store_be32(packet + 8, 2);
            ++stmProduced;
        });
        return;
    }
'''
changes += "replace(wrapper, '    if (stmSubmitted == 19) {', " + repr(dispatch + '    if (stmSubmitted == 19) {') + ")\n"
close = '''        if (fd == 20) {
            if (!m_sysconf.is_open() || m_sysconf.tellg() != 0x4000) {
                throw std::runtime_error("Laboratory CLOSE outside completed-read profile");
            }
            m_sysconf.close();
            if (m_sysconf.fail()) { throw std::runtime_error("Laboratory stream close failed"); }
            return IPC_OK;
        }
'''
changes += "fs = output / 'fs_device.cpp'\ntext = fs.read_text()\na = text.index('    int32_t close(')\nb = text.index('    int32_t read(', a)\nold = text[a:b]\nassert old.count('        if (fd == 20) { throw std::runtime_error(\"Laboratory file operation not yet verified\"); }') == 1\n"
changes += "replace(fs, old, old.replace('        if (fd == 20) { throw std::runtime_error(\"Laboratory file operation not yet verified\"); }', " + repr(close.rstrip()) + "))\n"
observer = '''    if (stmSubmitted == 22 && address == 0x802438b0) {
        std::cout << "SC_CLOSE_FREE" << std::hex << ' ' << context.gpr[3] << ' ' << context.gpr[4] << ' ' << context.msr << std::dec << '\\n';
    }
    if (stmSubmitted == 22 && (address == 0x80240680 || address == 0x80245af0 || address == 0x802478f0)) {
        std::cout << "SC_CLOSE_CALLBACK" << std::hex << ' ' << address << ' ' << context.gpr[3] << ' '
            << context.gpr[4] << ' ' << context.msr << std::dec << '\\n';
        for (bool cached : {false, true}) {
            std::cout << (cached ? "SC_CLOSE_REPLY_CACHED" : "SC_CLOSE_REPLY_PHYSICAL") << std::hex << ' ' << address << std::dec;
            for (unsigned index = 0; index < 64; ++index) {
                std::cout << ' ' << unsigned(bat_memory_read8(context, (cached ? 0x935e0080u : 0xd35e0080u) + index));
            }
            std::cout << '\\n';
        }
    }
    if (stmSubmitted == 22 && address == 0x80242430) {
        std::cout << "SC_PRODUCT_OPEN_ARGUMENTS" << std::hex << ' ' << context.gpr[3] << ' ' << context.gpr[4]
            << ' ' << context.gpr[5] << ' ' << context.gpr[6] << ' ' << context.msr << std::dec << '\\n';
        std::cout << "SC_PRODUCT_OPEN_PATH";
        for (unsigned index = 0; index < 64; ++index) {
            std::cout << ' ' << unsigned(bat_memory_read8(context, context.gpr[3] + index));
        }
        std::cout << '\\n';
    }
'''
changes += "replace(wrapper, '    original_trace_call(address, context);', " + repr(observer + '    original_trace_call(address, context);') + ")\n"
body = body[:start] + changes + body[end:]
body = body.replace("('output_62.cpp', 'output_67.cpp')", "('output_62.cpp', 'output_63.cpp', 'output_67.cpp')")
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp'")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_SYSCONF_CLOSE_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'\n    env['SHSM_SC_LAB_FILE'] = '_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF'\n    result = subprocess.run([str(exe),")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-sysconf-close-boot')
report = json.loads((output / 'build.json').read_text())
report['parentBuilderSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['laboratoryConsoleFileSha256'] = json.loads(Path('work/private-game/static-recomp/mass-sysconf-read-boot/build.json').read_text())['laboratoryConsoleFileSha256']
report['limits'] = ['First file CLOSE through unchanged shared kernel and existing stream, only after full read.',
    'PC X1/ticks/CSR guards retained; next product file/SC parsing/full retail and production settings policy unverified.']
(output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')

"""Finish product READ/CLOSE through existing scoped mechanisms; SC state remains original code."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-sysconf-product-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-sysconf-complete-boot'")
body = body.replace("('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_sysconf_close_boot.py', 'verify_sysconf_product_oracle.py')")
body = body.replace("'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'boot-quarantine.tsv'")
start = body.index("packet = output / 'ipc_open_packet.h'")
end = body.index('records = [dict(row)', start)
changes = "front = output / 'ipc_ack_frontend.h'\nwrapper = output / 'boot-wrapper.cpp'\nflush = output / 'flush_syscall.h'\nfs_source = runtime / 'src/hle/devices/fs_device.cpp'\n"
gate = '''    bool productTail = !std::getenv("SHSM_SC_PRODUCT_TAIL_DISABLED") && context.msr == 0x32 &&
        (stmSubmitted == 24 || stmSubmitted == 26) && context.lr == 0x80242240 && context.gpr[4] == 1 &&
        devices::experiment_stm_pending();
    if (productTail) {
        const uint32_t address = stmSubmitted == 24 ? 0x935e0080 : 0x935e00e0;
        const std::array<uint32_t, 10> expected = stmSubmitted == 24 ?
            std::array<uint32_t, 10>{3, 0, 3, 0x3800, 0x100, 1, 0x80540010, 0, 0x80240680, 0x935e1020} :
            std::array<uint32_t, 10>{2, 3, 3, 0x135e1180, 1, 0, 0, 0, 0x80240680, 0x935e1180};
        productTail &= context.gpr[3] == address + 32;
        for (unsigned index = 0; index < expected.size() && productTail; ++index) {
            productTail &= bat_memory_read32(context, address + index * 4) == expected[index];
        }
        const uint32_t work = stmSubmitted == 24 ? 0x935e1020 : 0x935e1180;
        productTail &= !productTail || (bat_memory_read32(context, work + 0x100) ==
            (stmSubmitted == 24 ? 0x802464b0u : 0x80245af0u) && bat_memory_read32(context, work + 0x104) == 0x804b3094);
    }
'''
changes += "replace(flush, '    bool sysconfPathFlush = false;', " + repr(gate + '    bool sysconfPathFlush = false;') + ")\n"
changes += "replace(flush, '&& !productFlush)', '&& !productFlush && !productTail)')\nreplace(flush, 'experimentFlushCallback = nestedRead || nestedClose || productFlush;', 'experimentFlushCallback = nestedRead || nestedClose || productFlush || productTail;')\n"
prior = '''    if ((stmSubmitted == 25 || stmSubmitted == 26) && message == 0x135e0080 && arm == 0x135e00e0 && devices::experiment_stm_pending()) { return true; }
    if ((stmSubmitted == 27 || stmSubmitted == 28) && message == 0x135e00e0 && arm == 0x135e0080 && devices::experiment_stm_pending()) { return true; }
'''
changes += "replace(front, '    if ((stmSubmitted == 23 || stmSubmitted == 24)', " + repr(prior + '    if ((stmSubmitted == 23 || stmSubmitted == 24)') + ")\n"
changes += "replace(front, '(stmSubmitted == 19 || stmSubmitted == 21 || stmSubmitted == 23)', '(stmSubmitted == 19 || stmSubmitted == 21 || stmSubmitted == 23 || stmSubmitted == 25 || stmSubmitted == 27)')\n"
changes += "replace(front, '(stmSubmitted == 18 || stmSubmitted == 19 || stmSubmitted == 20 || stmSubmitted == 21 || stmSubmitted == 22 || stmSubmitted == 23)', '(stmSubmitted >= 18 && stmSubmitted <= 27)')\n"
changes += "replace(front, '|| stmSubmitted == 23)', '|| stmSubmitted == 23 || stmSubmitted == 25 || stmSubmitted == 27)', 2)\n"
changes += "replace(front, '(stmSubmitted == 22 && !std::getenv(\"SHSM_SC_PRODUCT_DISABLED\")))', '(stmSubmitted == 22 && !std::getenv(\"SHSM_SC_PRODUCT_DISABLED\")) || ((stmSubmitted == 24 || stmSubmitted == 26) && !std::getenv(\"SHSM_SC_PRODUCT_TAIL_DISABLED\")))')\n"
changes += "replace(front, '&& value == 0x135e00e0)) &&', '&& value == 0x135e00e0) || (stmSubmitted == 24 && state.ppcMessage == 0x135e00e0 && value == 0x135e0080) || (stmSubmitted == 26 && state.ppcMessage == 0x135e0080 && value == 0x135e00e0)) &&')\n"
changes += "replace(front, '(stmSubmitted == 20 || stmSubmitted == 22 || stmSubmitted == 24)', '(stmSubmitted == 20 || stmSubmitted == 22 || stmSubmitted == 24 || stmSubmitted == 26 || stmSubmitted == 28)', 3)\n"
changes += "replace(output / 'si_external_delivery.h', '(stmSubmitted == 20 || stmSubmitted == 22 || stmSubmitted == 24)', '(stmSubmitted == 20 || stmSubmitted == 22 || stmSubmitted == 24 || stmSubmitted == 26 || stmSubmitted == 28)', 2)\n"
guard = '''            if (stmSubmitted == 24 || stmSubmitted == 26) {
                const uint32_t physical = stmSubmitted == 24 ? 0x135e0080 : 0x135e00e0;
                const std::array<uint32_t, 8> expected = stmSubmitted == 24 ?
                    std::array<uint32_t, 8>{3, 0, 3, 0x3800, 0x100, 1, 0x80540010, 0} :
                    std::array<uint32_t, 8>{2, 3, 3, 0x135e1180, 1, 0, 0, 0};
                if (context.msr != 0x32 || value != physical || !devices::experiment_stm_pending()) {
                    throw std::runtime_error("Product tail sender address/MSR/owner unverified");
                }
                for (unsigned index = 0; index < expected.size(); ++index) {
                    if (experiment_ipc_be32(context.mmu.get_ptr(value) + index * 4) != expected[index]) {
                        throw std::runtime_error("Product tail physical header unverified");
                    }
                }
            }
'''
changes += "replace(front, '            if (stmSubmitted == 22) {', " + repr(guard + '            if (stmSubmitted == 22) {') + ")\n"
dispatch = '''    if (stmSubmitted == 25 || stmSubmitted == 27) {
        const bool reading = stmSubmitted == 25;
        hw::ipc_ppc_ctrl = 0x30;
        EventScheduler::get().schedule_after(64, [](CPUContext&, uint64_t) {
            hw::ipc_ppc_ctrl = (hw::ipc_ppc_ctrl & ~1u) | 2;
        });
        hw::experiment_fixture_reply_after(request, 65, [request, reading](CPUContext& active, uint64_t) {
            auto* packet = experiment_ipc_mem1_span(active, request, 64);
            const std::array<uint32_t, 8> expected = reading ?
                std::array<uint32_t, 8>{3, 0, 3, 0x3800, 0x100, 1, 0x80540010, 0} :
                std::array<uint32_t, 8>{2, 3, 3, 0x135e1180, 1, 0, 0, 0};
            if (request != (reading ? 0x135e0080u : 0x135e00e0u) || !devices::experiment_stm_pending()) {
                throw std::runtime_error("Product tail producer address/owner unverified");
            }
            for (unsigned index = 0; index < expected.size(); ++index) {
                if (experiment_ipc_be32(packet + index * 4) != expected[index]) {
                    throw std::runtime_error("Product tail producer header unverified");
                }
            }
            const auto result = reading ? IOSKernel::get().read(active, 3, 0x3800, 0x100) : IOSKernel::get().close(active, 3);
            if (result != (reading ? 0x100 : IPC_OK)) {
                throw std::runtime_error("Product tail service result outside measured profile");
            }
            experiment_ipc_store_be32(packet, 8);
            experiment_ipc_store_be32(packet + 4, uint32_t(result));
            experiment_ipc_store_be32(packet + 8, reading ? 3 : 2);
            ++stmProduced;
        });
        return;
    }
'''
changes += "replace(wrapper, '    if (stmSubmitted == 23) {', " + repr(dispatch + '    if (stmSubmitted == 23) {') + ")\n"
observe = '''    if ((stmSubmitted == 26 || stmSubmitted == 28) && address == 0x802438b0) {
        std::cout << "SC_TAIL_FREE" << std::hex << ' ' << stmSubmitted << ' ' << context.gpr[3] << ' ' << context.gpr[4] << ' ' << context.msr << std::dec << '\\n';
    }
    if ((stmSubmitted == 26 || stmSubmitted == 28) && (address == 0x80240680 || address == 0x80247800 || address == 0x802478f0)) {
        std::cout << "SC_TAIL_CALLBACK" << std::hex << ' ' << stmSubmitted << ' ' << address << ' ' << context.gpr[3] << ' ' << context.gpr[4] << ' ' << context.msr << std::dec << '\\n';
        const uint32_t packet = stmSubmitted == 26 ? 0x935e0080 : 0x935e00e0;
        for (bool cached : {false, true}) {
            std::cout << (cached ? "SC_TAIL_REPLY_CACHED" : "SC_TAIL_REPLY_PHYSICAL") << std::hex << ' ' << stmSubmitted << ' ' << address << std::dec;
            for (unsigned index = 0; index < 64; ++index) {
                std::cout << ' ' << unsigned(bat_memory_read8(context, packet + index + (cached ? 0u : 0x40000000u)));
            }
            std::cout << '\\n';
        }
    }
'''
changes += "replace(wrapper, '    original_trace_call(address, context);', " + repr(observe + '    original_trace_call(address, context);') + ")\n"
status_observer = '''inline void experiment_sc_status_observe(CPUContext& context) {
    if (stmSubmitted == 28 && context.gpr[3] == 0) {
        std::cout << "SC_STATUS_ORIGINAL_RETURN" << std::hex << ' ' << context.gpr[3] << ' ' << context.msr
            << ' ' << unsigned(bat_memory_read8(context, 0x8052b008))
            << ' ' << unsigned(bat_memory_read8(context, 0x8052b01c))
            << ' ' << unsigned(bat_memory_read8(context, 0x8052b01e))
            << ' ' << bat_memory_read32(context, 0x804b2b4c) << ' ' << bat_memory_read32(context, 0x935e0004)
            << ' ' << bat_memory_read32(context, 0x804b2a80) << ' ' << bat_memory_read32(context, 0x804b2a84)
            << std::dec << '\\n';
        std::cout << "SC_STATUS_FRAME" << std::hex;
        for (uint32_t address : {0x804b3160u, 0x804b317cu, 0x804b3180u, 0x804b3158u,
            0x804b31a0u, 0x804b31a4u, 0x804b719cu}) {
            std::cout << ' ' << bat_memory_read32(context, address);
        }
        std::cout << std::dec << '\\n';
    }
}
'''
changes += "replace(front, 'inline unsigned stmSubmitted = 0;', " + repr('inline unsigned stmSubmitted = 0;\n' + status_observer) + ")\n"
snapshot = '''        std::cout << "SC_COMPLETE_STATE" << std::hex;
        for (uint32_t address : {0x8052b008u, 0x804b3180u, 0x804b3184u, 0x804b3188u, 0x804b2b4cu, 0x935e0004u}) {
            std::cout << ' ' << nwii::runtime::bat_memory_read32(context, address);
        }
        std::cout << std::dec << '\\n';
        for (bool cached : {false, true}) {
            std::cout << (cached ? "SC_COMPLETE_PRODUCT_CACHED" : "SC_COMPLETE_PRODUCT_PHYSICAL");
            for (unsigned index = 0; index < 256; ++index) {
                std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context, (cached ? 0x80003800u : 0xc0003800u) + index));
            }
            std::cout << '\\n';
        }
        for (bool cached : {false, true}) {
            std::cout << (cached ? "SC_COMPLETE_CONF_CACHED" : "SC_COMPLETE_CONF_PHYSICAL");
            for (unsigned index = 0; index < 0x4000; ++index) {
                std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context, (cached ? 0x804b31a0u : 0xc04b31a0u) + index));
            }
            std::cout << '\\n';
        }
        if (nwii::runtime::stmSubmitted == 28) {
            std::cout << "SC_COMPLETE_NEXT_PACKET";
            for (unsigned index = 0; index < 64; ++index) {
                std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context, 0xd35e0080 + index));
            }
            std::cout << '\\n';
            const auto physical = nwii::runtime::bat_memory_read32(context, 0xd35e008c);
            if (nwii::runtime::bat_memory_read32(context, 0xd35e0080) == 1 &&
                ((physical >= 0x400000 && physical < 0x1800000 - 64) ||
                (physical >= 0x135e1000 && physical < 0x13600000 - 64))) {
                std::cout << "SC_COMPLETE_NEXT_PATH";
                for (unsigned index = 0; index < 64; ++index) {
                    std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context, 0xc0000000 + physical + index));
                }
                std::cout << '\\n';
            }
        }
'''
changes += "replace(output / 'mass_boot.cpp', '        std::cout << \"BOOT_ES_LAYOUT \"', " + repr(snapshot + '        std::cout << "BOOT_ES_LAYOUT "') + ")\n"
body = body[:start] + changes + body[end:]
body = body.replace("('output_62.cpp', 'output_67.cpp')", "('output_62.cpp', 'output_63.cpp', 'output_67.cpp', 'output_68.cpp')")
body = body.replace("    source.write_bytes(Path(row['source']).read_bytes())", "    source.write_bytes(Path(row['source']).read_bytes())\n    if name == 'output_68.cpp':\n        replace(source, 'loc_80247608: ;', 'loc_80247608: ;\\n    nwii::runtime::experiment_sc_status_observe(ctx);')")
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp'")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_SC_PRODUCT_TAIL_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'\n    env['SHSM_SC_LAB_FILE'] = '_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF'\n    env['SHSM_SC_LAB_PRODUCT'] = '_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt'\n    result = subprocess.run([str(exe),")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-sysconf-complete-boot')
report = json.loads((output / 'build.json').read_text())
report['parentBuilderSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['laboratoryConsoleFileSha256'] = json.loads(Path('work/private-game/static-recomp/mass-sysconf-product-boot/build.json').read_text())['laboratoryConsoleFileSha256']
report['laboratoryProductSha256'] = json.loads(Path('work/private-game/static-recomp/mass-sysconf-product-boot/build.json').read_text())['laboratoryProductSha256']
report['limits'] = ['Actual product READ/CLOSE using existing stream/kernel; SC callbacks/state are never host-written.',
    'Completion must be separately verified; laboratory files, PC handshake/timing are not public runtime dependencies/physical proof.']
(output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')

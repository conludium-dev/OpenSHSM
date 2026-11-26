"""Read-only product-file OPEN through the same FS stream, registry and reentrant IPC."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-sysconf-close-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-sysconf-product-boot'")
body = body.replace("('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_sysconf_close_boot.py', 'verify_sysconf_product_oracle.py')")
body = body.replace("'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'boot-quarantine.tsv'")
start = body.index("packet = output / 'ipc_open_packet.h'")
end = body.index('records = [dict(row)', start)
changes = "front = output / 'ipc_ack_frontend.h'\nwrapper = output / 'boot-wrapper.cpp'\nflush = output / 'flush_syscall.h'\nfs_source = runtime / 'src/hle/devices/fs_device.cpp'\n"
gate = '''    bool productFlush = !std::getenv("SHSM_SC_PRODUCT_DISABLED") && context.msr == 0x32 && stmSubmitted == 22 &&
        devices::experiment_stm_pending() && (context.lr == 0x8024250c || context.lr == 0x80242240);
    if (productFlush) {
        const std::string path = "/title/00000001/00000002/data/setting.txt";
        for (unsigned index = 0; index <= path.size(); ++index) {
            productFlush &= bat_memory_read8(context, 0x935e1180 + index) ==
                (index < path.size() ? uint8_t(path[index]) : 0);
        }
        productFlush &= bat_memory_read32(context, 0x935e0100) == 0x80240680 &&
            bat_memory_read32(context, 0x935e0104) == 0x935e1180 &&
            bat_memory_read32(context, 0x935e1280) == 0x80244e30 &&
            bat_memory_read32(context, 0x935e1284) == 0x804b3094;
        productFlush &= (context.lr == 0x8024250c && context.gpr[3] == 0x935e11c0 && context.gpr[4] == 2) ||
            (context.lr == 0x80242240 && context.gpr[3] == 0x935e0100 && context.gpr[4] == 1);
    }
'''
changes += "replace(flush, '    bool sysconfPathFlush = false;', " + repr(gate + '    bool sysconfPathFlush = false;') + ")\n"
changes += "replace(flush, '&& !nestedClose)', '&& !nestedClose && !productFlush)')\nreplace(flush, 'experimentFlushCallback = nestedRead || nestedClose;', 'experimentFlushCallback = nestedRead || nestedClose || productFlush;')\n"
changes += "replace(front, '    if ((stmSubmitted == 21 || stmSubmitted == 22)', '    if ((stmSubmitted == 23 || stmSubmitted == 24) && message == 0x135e00e0 && arm == 0x135e0080 && devices::experiment_stm_pending()) { return true; }\\n    if ((stmSubmitted == 21 || stmSubmitted == 22)')\n"
changes += "replace(front, '(stmSubmitted == 19 || stmSubmitted == 21)', '(stmSubmitted == 19 || stmSubmitted == 21 || stmSubmitted == 23)')\n"
changes += "replace(front, '(stmSubmitted == 18 || stmSubmitted == 19 || stmSubmitted == 20 || stmSubmitted == 21)', '(stmSubmitted == 18 || stmSubmitted == 19 || stmSubmitted == 20 || stmSubmitted == 21 || stmSubmitted == 22 || stmSubmitted == 23)')\n"
changes += "replace(front, '|| stmSubmitted == 21)', '|| stmSubmitted == 21 || stmSubmitted == 23)', 2)\n"
changes += "replace(front, '(stmSubmitted == 20 && !std::getenv(\"SHSM_SYSCONF_CLOSE_DISABLED\")))', '(stmSubmitted == 20 && !std::getenv(\"SHSM_SYSCONF_CLOSE_DISABLED\")) || (stmSubmitted == 22 && !std::getenv(\"SHSM_SC_PRODUCT_DISABLED\")))')\n"
changes += "replace(front, '&& value == 0x135e0080)) &&', '&& value == 0x135e0080) || (stmSubmitted == 22 && state.ppcMessage == 0x135e0080 && value == 0x135e00e0)) &&')\n"
changes += "replace(front, '(stmSubmitted == 20 || stmSubmitted == 22)', '(stmSubmitted == 20 || stmSubmitted == 22 || stmSubmitted == 24)', 3)\n"
changes += "replace(output / 'si_external_delivery.h', '(stmSubmitted == 20 || stmSubmitted == 22)', '(stmSubmitted == 20 || stmSubmitted == 22 || stmSubmitted == 24)', 2)\n"
guard = '''            if (stmSubmitted == 22) {
                const std::array<uint32_t, 8> expected{1, 0x4000, 0, 0x135e1180, 1, 0, 0, 0};
                if (context.msr != 0x32 || value != 0x135e00e0 || !devices::experiment_stm_pending()) {
                    throw std::runtime_error("Product OPEN address/MSR/pending owner unverified");
                }
                for (unsigned index = 0; index < expected.size(); ++index) {
                    if (experiment_ipc_be32(context.mmu.get_ptr(value) + index * 4) != expected[index]) {
                        throw std::runtime_error("Product OPEN physical header unverified");
                    }
                }
            }
'''
changes += "replace(front, '            if (stmSubmitted == 20) {', " + repr(guard + '            if (stmSubmitted == 20) {') + ")\n"
dispatch = '''    if (stmSubmitted == 23) {
        hw::ipc_ppc_ctrl = 0x30;
        EventScheduler::get().schedule_after(64, [](CPUContext&, uint64_t) {
            hw::ipc_ppc_ctrl = (hw::ipc_ppc_ctrl & ~1u) | 2;
        });
        hw::experiment_fixture_reply_after(request, 65, [request](CPUContext& active, uint64_t) {
            experiment_ipc_open_packet(active, request);
            ++stmProduced;
        });
        return;
    }
'''
changes += "replace(wrapper, '    if (stmSubmitted == 21) {', " + repr(dispatch + '    if (stmSubmitted == 21) {') + ")\n"
changes += "packet = output / 'ipc_open_packet.h'\nreplace(packet, '    if (length == 1 && physical >= 0x135e1020', '    if (length == 1 && physical >= 0x135e1180 && physical < 0x135e11aa) { return context.mmu.get_ptr(physical); }\\n    if (length == 1 && physical >= 0x135e1020')\n"
changes += "replace(packet, 'path != \"/shared2/sys/SYSCONF\"', '(path != \"/shared2/sys/SYSCONF\" && path != \"/title/00000001/00000002/data/setting.txt\")', 2)\n"
changes += "replace(packet, 'if (path == \"/shared2/sys/SYSCONF\" && mode != 1)', 'if ((path == \"/shared2/sys/SYSCONF\" || path == \"/title/00000001/00000002/data/setting.txt\") && mode != 1)')\n"
changes += "fs = output / 'fs_device.cpp'\nreplace(fs, '    std::ifstream m_sysconf;', '    std::ifstream m_sysconf;\\n    uint32_t m_readLength = 0x4000;\\n    uint32_t m_readTarget = 0x4b31a0;')\n"
changes += "replace(fs, 'path != \"/shared2/sys/SYSCONF\" || mode != 1', '(path != \"/shared2/sys/SYSCONF\" && path != \"/title/00000001/00000002/data/setting.txt\") || mode != 1')\n"
changes += "replace(fs, '        const auto* source = std::getenv(\"SHSM_SC_LAB_FILE\");', '        const bool product = path == \"/title/00000001/00000002/data/setting.txt\";\\n        const uint32_t length = product ? 0x100 : 0x4000;\\n        const auto* source = std::getenv(product ? \"SHSM_SC_LAB_PRODUCT\" : \"SHSM_SC_LAB_FILE\");')\n"
changes += "replace(fs, 'm_sysconf.seekg(0, std::ios::end).tellg() != 0x4000', 'm_sysconf.seekg(0, std::ios::end).tellg() != length')\n"
changes += "replace(fs, '        std::array<char, 4> head{}, tail{};', '        if (!product) {\\n        std::array<char, 4> head{}, tail{};')\n"
changes += "replace(fs, '        m_sysconf.seekg(0);\\n        return 20;', '        }\\n        m_sysconf.seekg(0);\\n        m_readLength = length;\\n        m_readTarget = product ? 0x3800 : 0x4b31a0;\\n        return 20;')\n"
changes += "replace(fs, 'm_sysconf.tellg() != 0x4000', 'm_sysconf.tellg() != m_readLength')\nreplace(fs, 'buf != 0x4b31a0 || len != 0x4000', 'buf != m_readTarget || len != m_readLength')\nreplace(fs, 'm_sysconf.read(data.data(), data.size());', 'm_sysconf.read(data.data(), len);')\nreplace(fs, 'm_sysconf.gcount() != 0x4000', 'm_sysconf.gcount() != len')\nreplace(fs, 'std::memcpy(destination, data.data(), data.size());', 'std::memcpy(destination, data.data(), len);')\n"
changes += "fs_text = fs.read_text()\na = fs_text.index('        if (!product) {\\n')\nb = fs_text.index('        }\\n        m_sysconf.seekg(0);\\n        m_readLength', a)\nblock = fs_text[a:b]\nparts = block.splitlines(keepends=True)\nreplace(fs, block, parts[0] + ''.join('    ' + line for line in parts[1:]))\n"
observe = '''    if (stmSubmitted == 24 && address == 0x802438b0) {
        std::cout << "SC_PRODUCT_FREE" << std::hex << ' ' << context.gpr[3] << ' ' << context.gpr[4] << ' ' << context.msr << std::dec << '\\n';
    }
    if (stmSubmitted == 24 && (address == 0x80240680 || address == 0x80244e30 || address == 0x80247730)) {
        std::cout << "SC_PRODUCT_CALLBACK" << std::hex << ' ' << address << ' ' << context.gpr[3] << ' ' << context.gpr[4] << ' ' << context.msr << std::dec << '\\n';
        for (bool cached : {false, true}) {
            std::cout << (cached ? "SC_PRODUCT_REPLY_CACHED" : "SC_PRODUCT_REPLY_PHYSICAL") << std::hex << ' ' << address << std::dec;
            for (unsigned index = 0; index < 64; ++index) {
                std::cout << ' ' << unsigned(bat_memory_read8(context, (cached ? 0x935e00e0u : 0xd35e00e0u) + index));
            }
            std::cout << '\\n';
        }
    }
'''
changes += "replace(wrapper, '    original_trace_call(address, context);', " + repr(observe + '    original_trace_call(address, context);') + ")\n"
body = body[:start] + changes + body[end:]
body = body.replace("('output_62.cpp', 'output_67.cpp')", "('output_62.cpp', 'output_63.cpp', 'output_67.cpp')")
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp'")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_SC_PRODUCT_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'\n    env['SHSM_SC_LAB_FILE'] = '_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF'\n    env['SHSM_SC_LAB_PRODUCT'] = '_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt'\n    result = subprocess.run([str(exe),")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-sysconf-product-boot')
report = json.loads((output / 'build.json').read_text())
report['parentBuilderSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['laboratoryConsoleFileSha256'] = json.loads(Path('work/private-game/static-recomp/mass-sysconf-close-boot/build.json').read_text())['laboratoryConsoleFileSha256']
report['laboratoryProductSha256'] = hashlib.sha256(Path('_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt').read_bytes()).hexdigest()
report['limits'] = ['Product OPEN uses same existing read-only stream/internal handle/shared registry and explicit lab source.',
    'Product READ/CLOSE not submitted yet; PC timing/handshake and console provenance remain adaptations, not physical retail proof.']
(output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')

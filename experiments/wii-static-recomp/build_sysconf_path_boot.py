"""Admit only the measured first SYSCONF path flush; file submission stays guarded."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-es-close-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-sysconf-path-boot'")
body = body.replace("('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_es_close_boot.py', 'verify_sysconf_events.py', 'verify_sysconf_payload.py')")
body = body.replace("'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'boot-quarantine.tsv'")
start = body.index("packet = output / 'ipc_open_packet.h'")
end = body.index('records = [dict(row)', start)
admission = '''    bool sysconfPathFlush = false;
    if (!std::getenv("SHSM_SYSCONF_PATH_DISABLED") && context.msr == 0xa032 && stmSubmitted == 16 &&
        context.lr == 0x8024250c && context.gpr[3] == 0x935e1040 && context.gpr[4] == 1 &&
        context.gpr[27] == 0x935e1020 && context.gpr[29] == 0x80240680 && context.gpr[31] == 0x935e0080 &&
        devices::experiment_stm_pending()) {
        const std::string path = "/shared2/sys/SYSCONF";
        sysconfPathFlush = true;
        for (unsigned index = 0; index <= path.size(); ++index) {
            sysconfPathFlush &= bat_memory_read8(context, 0x935e1020 + index) ==
                (index < path.size() ? uint8_t(path[index]) : 0);
        }
        sysconfPathFlush &= bat_memory_read32(context, 0x935e1120) == 0x80244e30 &&
            bat_memory_read32(context, 0x935e1124) == 0x804b3094 &&
            bat_memory_read32(context, 0x935e1128) == 0 &&
            bat_memory_read32(context, 0x935e00a0) == 0x80240680 &&
            bat_memory_read32(context, 0x935e00a4) == 0x935e1020;
    }
    if (stmSubmitted == 16 && context.lr == 0x8024250c) {
        std::cout << "SC_PATH_GATE " << sysconfPathFlush << ' ' << experimentFlushEe << ' '
            << (hw::pi_intsr.load() & hw::pi_intmr.load()) << ' ' << context.in_callback << ' '
            << context.callback_depth << ' ' << context.backup_stack.size() << ' ' << context.dispatch_saved_ctx << ' '
            << context.ext_resched_pending << ' ' << context.exception_pc << ' ' << context.vblank_pending.load() << ' '
            << context.dec_irq_pending << ' ' << context.pending_cb_count.load() << ' ' << context.pending_callbacks.size() << '\\n';
    }
'''
changes = "front = output / 'ipc_ack_frontend.h'\nflush = output / 'flush_syscall.h'\nwrapper = output / 'boot-wrapper.cpp'\n"
changes += "replace(flush, '    bool dataDirFlush = false;', " + repr(admission + '    bool dataDirFlush = false;') + ")\n"
changes += "replace(flush, '&& !titleFlush && !dataDirFlush)', '&& !titleFlush && !dataDirFlush && !sysconfPathFlush)')\n"
changes += "fs_source = runtime / 'src/hle/devices/fs_device.cpp'\n"
observer = '''        if (nwii::runtime::stmSubmitted == 16) {
            for (bool cached : {false, true}) {
                std::cout << (cached ? "SC_PATH_PACKET_CACHED" : "SC_PATH_PACKET_PHYSICAL");
                for (unsigned index = 0; index < 64; ++index) {
                    std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context,
                        (cached ? 0x935e0080u : 0xd35e0080u) + index));
                }
                std::cout << '\\n';
            }
            std::cout << "SC_PATH_BYTES_PHYSICAL";
            for (unsigned index = 0; index < 32; ++index) {
                std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context, 0xd35e1020 + index));
            }
            std::cout << '\\n';
        }
'''
changes += "replace(output / 'mass_boot.cpp', '        std::cout << \"BOOT_ES_LAYOUT \"', " + repr(observer + '        std::cout << "BOOT_ES_LAYOUT "') + ")\n"
body = body[:start] + changes + body[end:]
body = body.replace("('output_62.cpp', 'output_67.cpp')", "('output_62.cpp', 'output_63.cpp', 'output_67.cpp')")
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp'")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_SYSCONF_PATH_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'\n    result = subprocess.run([str(exe),")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-sysconf-path-boot')
report = json.loads((output / 'build.json').read_text())
report['parentBuilderSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Only the first SYSCONF path flush, measured callback/work/path preconditions; file submission remains guarded.',
    'No file data, descriptor, IOS response, callback, new runtime or registry is fabricated.']
(output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')

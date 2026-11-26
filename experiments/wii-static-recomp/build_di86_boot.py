"""Integrate only original-measured DI86 through existing DI class/kernel/events."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-di-open-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-di86-boot'").replace(
    "('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('verify_di86_events_dolphin.py',)").replace(
    "'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'di_device.cpp', 'boot-quarantine.tsv'")
start, end = body.index("packet = output / 'ipc_open_packet.h'"), body.index('records = [dict(row)')
changes = "front = output / 'ipc_ack_frontend.h'\nwrapper = output / 'boot-wrapper.cpp'\nfs_source = runtime / 'src/hle/devices/fs_device.cpp'\n(output / 'di86_adapter.h').write_bytes((experiment / 'di86_adapter.h').read_bytes())\n"
changes += "replace(front, '#include \"ipc_startup_frontend.h\"', '#include \"ipc_startup_frontend.h\"\\n#include \"di86_adapter.h\"')\n"
odd = '(stmSubmitted == 1 || stmSubmitted == 3 || stmSubmitted == 5 || stmSubmitted == 7 || stmSubmitted == 9 || stmSubmitted == 11 || stmSubmitted == 13 || stmSubmitted == 15 || stmSubmitted == 17 || stmSubmitted == 19 || stmSubmitted == 21 || stmSubmitted == 23 || stmSubmitted == 25 || stmSubmitted == 27 || stmSubmitted == 29)'
changes += 'replace(front, ' + repr(odd) + ', ' + repr(odd[:-1] + ' || stmSubmitted == 31)') + ', 2)\n'
even = '(stmSubmitted == 20 || stmSubmitted == 22 || stmSubmitted == 24 || stmSubmitted == 26 || stmSubmitted == 28 || stmSubmitted == 30)'
changes += 'replace(front, ' + repr(even) + ', ' + repr(even[:-1] + ' || stmSubmitted == 32)') + ', 3)\n'
changes += "replace(output / 'si_external_delivery.h', '|| stmSubmitted == 30)', '|| stmSubmitted == 30 || stmSubmitted == 32)', 2)\n"
changes += "replace(front, '!std::getenv(\"SHSM_DI_OPEN_DISABLED\")))', '!std::getenv(\"SHSM_DI_OPEN_DISABLED\")) || (stmSubmitted == 30 && !std::getenv(\"SHSM_DI86_DISABLED\")))')\n"
changes += "replace(front, '            if (stmSubmitted == 28) {', '            if (stmSubmitted == 30) {\\n                experiment_di86_validate(context, value);\\n            }\\n            if (stmSubmitted == 28) {')\n"
dispatch = '''    if (stmSubmitted == 31) {
        hw::ipc_ppc_ctrl = 0x31;
        EventScheduler::get().schedule_after(64, [](CPUContext&, uint64_t) {
            hw::ipc_ppc_ctrl = (hw::ipc_ppc_ctrl & ~1u) | 2;
        });
        hw::experiment_fixture_reply_after(request, 65, [request](CPUContext& active, uint64_t) {
            experiment_di86_dispatch(active, request);
            ++stmProduced;
        });
        return;
    }
'''
changes += "replace(wrapper, '    if (stmSubmitted == 25 ||', " + repr(dispatch + '    if (stmSubmitted == 25 ||') + ")\n"
method = '''    int32_t ioctl(CPUContext& context, const IpcRequest& request) override {
        if (request.cmd != 6 || request.fd != 3 || request.req_addr != 0x135e0080 || request.ioctl_cmd != 0x86 ||
            request.in_buf != 0x135e2560 || request.in_size != 32 || request.out_buf || request.out_size) {
            throw std::runtime_error("DI command outside measured DI86 profile");
        }
        const auto* first = context.mmu.get_ptr(request.in_buf);
        const auto* last = context.mmu.get_ptr(request.in_buf + 31);
        if (!first || last != first + 31 || first[0] != 0x86) {
            throw std::runtime_error("DI86 command buffer unverified");
        }
        for (unsigned index = 1; index < 32; ++index) {
            if (first[index]) {
                throw std::runtime_error("DI86 command tail unverified");
            }
        }
        return 1;
    }
'''
changes += "replace(output / 'di_device.cpp', '    int32_t ioctl(CPUContext&, const IpcRequest&) override { throw std::runtime_error(\"DI IOCTL unverified\"); }', " + repr(method.rstrip()) + ")\n"
observer = '''inline void experiment_di86_observe(CPUContext& context, unsigned kind) {
    if ((kind == 4 && (stmSubmitted == 31 || stmSubmitted == 32)) || (kind != 4 && stmSubmitted == 32)) {
        std::cout << "DI86_SOURCE" << std::hex << ' ' << kind << ' ' << context.gpr[3] << ' ' << context.gpr[4] << ' ' << context.msr
            << ' ' << unsigned(bat_memory_read8(context, 0x8052ac78)) << ' ' << unsigned(bat_memory_read8(context, 0x804983a8))
            << ' ' << bat_memory_read32(context, 0x804b2b4c) << std::dec << '\\n';
        for (bool cached : {false, true}) {
            std::cout << (cached ? "DI86_REPLY_CACHED" : "DI86_REPLY_PHYSICAL") << ' ' << kind;
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
body = body.replace("    source.write_bytes(Path(row['source']).read_bytes())", "    source.write_bytes(Path(row['source']).read_bytes())\n    if name == 'output_65.cpp':\n        for label, kind in [('loc_80227F20: ;', 4), ('loc_802258A0: ;', 2), ('loc_80225940: ;', 3)]:\n            replace(source, label, label + '\\n    nwii::runtime::experiment_di86_observe(ctx, ' + str(kind) + ');')")
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp', output / 'di_device.cpp'")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_DI86_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'\n    env['SHSM_SC_LAB_FILE'] = '_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF'\n    env['SHSM_SC_LAB_PRODUCT'] = '_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt'\n    result = subprocess.run([str(exe),")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-di86-boot')
report = json.loads((output / 'build.json').read_text())
report['limits'] = ['Exact first DI86 no-output service response1 measured in original SDK oracle; all other DI commands refuse.',
    'Original callback/state/free behavior requires separate audit; PC event timing not physical-drive/cycle proof.']
(output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')

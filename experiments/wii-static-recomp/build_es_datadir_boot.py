"""Extend the existing native ES profile for the measured first GetDataDir only."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-es-title-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-es-datadir-boot'")
body = body.replace("('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_es_title_boot.py', 'verify_es_datadir_disc.py')")
body = body.replace("'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'boot-quarantine.tsv'")
start = body.index("packet = output / 'ipc_open_packet.h'")
end = body.index('records = [dict(row)', start)
changes = '''
(output / 'es_datadir_adapter.h').write_bytes((experiment / 'es_datadir_adapter.h').read_bytes())
front = output / 'ipc_ack_frontend.h'
replace(front, '|| stmSubmitted == 11)', '|| stmSubmitted == 11 || stmSubmitted == 13)', 2)
replace(front, '(stmSubmitted == 10 && !std::getenv("SHSM_ES_TITLE_DISABLED")))',
    '(stmSubmitted == 10 && !std::getenv("SHSM_ES_TITLE_DISABLED")) || (stmSubmitted == 12 && !std::getenv("SHSM_ES_DATADIR_DISABLED")))')
'''
admission = '''            if (stmSubmitted == 12) {
                const auto* packet = context.mmu.get_ptr(value);
                const std::array<uint32_t, 8> expected{7, 0, 3, 0x1d, 1, 1, 0x540010, 0};
                if (value != 0x135e0080 || !devices::experiment_stm_pending()) {
                    throw std::runtime_error("ES data-dir sender/pending owner unverified");
                }
                for (unsigned index = 0; index < expected.size(); ++index) {
                    if (experiment_ipc_be32(packet + index * 4) != expected[index]) {
                        throw std::runtime_error("ES data-dir sender physical header unverified");
                    }
                }
            }
'''
changes += "replace(front, '            if (stmSubmitted == 4) {', " + repr(admission + '            if (stmSubmitted == 4) {') + ")\n"
flush = '''    bool dataDirFlush = false;
    if (!std::getenv("SHSM_ES_DATADIR_DISABLED") && context.msr == 0xa032 && stmSubmitted == 12 &&
        context.gpr[29] == 0x935e0080 && context.gpr[30] == 0x80540010 && context.gpr[4] == 1 &&
        devices::experiment_stm_pending()) {
        const std::array<uint32_t, 7> expected{7, 0, 3, 0x1d, 1, 1, 0x80540010};
        dataDirFlush = true;
        for (unsigned index = 0; index < expected.size(); ++index) {
            dataDirFlush &= bat_memory_read32(context, 0x935e0080 + index * 4) == expected[index];
        }
        const auto input = bat_memory_read32(context, 0x80540010);
        const auto output = bat_memory_read32(context, 0x80540018);
        dataDirFlush &= bat_memory_read32(context, 0x80540014) == 8 &&
            bat_memory_read32(context, 0x8054001c) == 30;
        dataDirFlush &= (context.lr == 0x80242fc8 && context.gpr[3] == 0x804b2ce0 && input == 0x8053ff40 && output == 0x804b2cc0) ||
            (context.lr == 0x80243020 && context.gpr[3] == 0x8053ff60 && input == 0x8053ff40 && output == 0x4b2cc0) ||
            (context.lr == 0x80243068 && context.gpr[3] == 0x80540030 && input == 0x53ff40 && output == 0x4b2cc0);
    }
'''
changes += "flush_path = output / 'flush_syscall.h'\nreplace(flush_path, '    bool titleFlush = false;', " + repr(flush + '    bool titleFlush = false;') + ")\n"
changes += "replace(flush_path, '&& !titleFlush)', '&& !titleFlush && !dataDirFlush)')\n"
changes += '''wrapper = output / 'boot-wrapper.cpp'
replace(wrapper, '#include "es_title_adapter.h"', '#include "es_title_adapter.h"\\n#include "es_datadir_adapter.h"')
'''
producer = '''    if (stmSubmitted == 13) {
        hw::experiment_fixture_reply_after(request, 2, [request](CPUContext& active, uint64_t) {
            experiment_es_datadir_dispatch(active, request);
            ++stmProduced;
        });
        return;
    }
'''
changes += "replace(wrapper, '    if (stmSubmitted == 11) {', " + repr(producer + '    if (stmSubmitted == 11) {') + ")\n"
changes += "replace(wrapper, 'inline bool experimentTitleCaptured = false;', 'inline bool experimentTitleCaptured = false;\\ninline bool experimentDataDirBefore = false;\\ninline bool experimentDataDirCaptured = false;')\n"
observe = '''    if (address == 0x80249ba0 && stmSubmitted == 12 && !experimentDataDirBefore) {
        experimentDataDirBefore = true;
        std::cout << "BOOT_DATADIR_ARGS" << std::hex << ' ' << context.gpr[3] << ' ' << context.gpr[4]
            << ' ' << context.gpr[5] << std::dec << '\\n';
        std::cout << "BOOT_DATADIR_BEFORE";
        for (unsigned index = 0; index < 32; ++index) {
            std::cout << ' ' << unsigned(bat_memory_read8(context, 0x804b2cc0 + index));
        }
        std::cout << '\\n';
    }
    if (address == 0x8019d564 && context.lr == 0x8024635c && stmSubmitted == 14 && stmProduced == 6 && !experimentDataDirCaptured) {
        experimentDataDirCaptured = true;
        std::cout << "BOOT_DATADIR_CONTINUATION" << std::hex << ' ' << address << ' ' << context.lr << std::dec << '\\n';
        for (bool cached : {false, true}) {
            for (auto [label, physical, length] : {std::tuple<const char*, uint32_t, unsigned>{"OUTPUT", 0x4b2cc0, 32},
                {"INPUT", 0x53ff40, 8}, {"VECTOR", 0x540010, 16}, {"REPLY", 0x135e0080, 64}}) {
                std::cout << "BOOT_DATADIR_" << label << (cached ? "_CACHED" : "_PHYSICAL");
                for (unsigned index = 0; index < length; ++index) {
                    std::cout << ' ' << unsigned(bat_memory_read8(context, physical + index +
                        (cached ? 0x80000000 : 0xc0000000)));
                }
                std::cout << '\\n';
            }
        }
        std::cout << "BOOT_DATADIR_HEAP" << std::hex << ' ' << bat_memory_read32(context, 0x804b2b4c)
            << ' ' << bat_memory_read32(context, 0x935e0004) << std::dec << '\\n';
    }
'''
changes += "replace(wrapper, '    original_trace_call(address, context);', " + repr(observe + '    original_trace_call(address, context);') + ")\n"
changes += '''es_source = output / 'es_device.cpp'
replace(es_source, '#include "es_title_adapter.h"', '#include "es_datadir_adapter.h"')
'''
service = '''        if (req.ioctl_cmd == 0x1d) {
            return experiment_es_datadir_write(context, req, title_);
        }
'''
changes += "replace(es_source, '        if (req.cmd != 7', " + repr(service + '        if (req.cmd != 7') + ")\n"
changes += "fs_source = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime/src/hle/devices/es_device.cpp')\n"
body = body[:start] + changes + body[end:]
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp'")
body = body.replace("for name in ('output_62.cpp', 'output_67.cpp'):", "for name in ('output_62.cpp', 'output_63.cpp', 'output_67.cpp'):")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_ES_DATADIR_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'\n    result = subprocess.run([str(exe),")
body = body.replace("'vendorFsSha256': sha(fs_source)", "'vendorEsSha256': sha(fs_source)")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-es-datadir-boot')
report = json.loads((output / 'build.json').read_text())
report['parentBuilderSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['adapterSha256'] = hashlib.sha256((experiment / 'es_datadir_adapter.h').read_bytes()).hexdigest()
report['tmdSha256'] = hashlib.sha256(Path('work/private-game/disc/DATA/tmd.bin').read_bytes()).hexdigest()
report['limits'] = ['Exactly first IOCTLV1D/title8/output30 profile; actual metadata-backed existing device writes29 bytes and preserves byte30.',
    'Existing title query retained; no file/save writes, arbitrary titles/vectors, credentials, callback completion, timing or gameplay proof.']
(output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')

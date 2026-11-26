"""Integrate measured title-vector flush/production on the existing native ES profile."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text()
body = body.replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-es-open-boot'")
body = body.replace("output = root / 'mass-fs-open-boot'", "output = root / 'mass-es-title-boot'")
body = body.replace("('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_es_open_boot.py', 'verify_es_disc_oracle.py', 'verify_es_vector_observation.py')")
body = body.replace("'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'boot-quarantine.tsv'")
start = body.index("packet = output / 'ipc_open_packet.h'")
end = body.index('records = [dict(row)', start)
changes = """
(output / 'es_title_adapter.h').write_bytes((experiment / 'es_title_adapter.h').read_bytes())
front = output / 'ipc_ack_frontend.h'
replace(front, '(stmSubmitted == 1 || stmSubmitted == 3 || stmSubmitted == 5 || stmSubmitted == 7 || stmSubmitted == 9)',
    '(stmSubmitted == 1 || stmSubmitted == 3 || stmSubmitted == 5 || stmSubmitted == 7 || stmSubmitted == 9 || stmSubmitted == 11)', 2)
replace(front, '(stmSubmitted == 8 && !std::getenv("SHSM_ES_OPEN_DISABLED")))',
    '(stmSubmitted == 8 && !std::getenv("SHSM_ES_OPEN_DISABLED")) || (stmSubmitted == 10 && !std::getenv("SHSM_ES_TITLE_DISABLED")))')
"""
admission = """            if (stmSubmitted == 10) {
                const auto* packet = context.mmu.get_ptr(value);
                const std::array<uint32_t, 8> expected{7, 3, 3, 0x20, 0, 1, 0x53fff0, 0};
                if (value != 0x135e0080 || !devices::experiment_stm_pending()) {
                    throw std::runtime_error("ES title sender/pending owner unverified");
                }
                for (unsigned index = 0; index < expected.size(); ++index) {
                    if (experiment_ipc_be32(packet + index * 4) != expected[index]) {
                        throw std::runtime_error("ES title sender physical header unverified");
                    }
                }
            }
"""
changes += "replace(front, '            if (stmSubmitted == 4) {', " + repr(admission + '            if (stmSubmitted == 4) {') + ")\n"
flush = """    bool titleFlush = false;
    if (!std::getenv("SHSM_ES_TITLE_DISABLED") && context.msr == 0xa032 && stmSubmitted == 10 &&
        context.gpr[29] == 0x935e0080 && context.gpr[30] == 0x8053fff0 && context.gpr[4] == 1 &&
        devices::experiment_stm_pending() && (context.lr == 0x80242fc8 || context.lr == 0x80243068)) {
        const std::array<uint32_t, 7> expected{7, 3, 3, 0x20, 0, 1, 0x8053fff0};
        titleFlush = true;
        for (unsigned index = 0; index < expected.size(); ++index) {
            titleFlush &= bat_memory_read32(context, 0x935e0080 + index * 4) == expected[index];
        }
        const auto address = bat_memory_read32(context, 0x8053fff0);
        titleFlush &= bat_memory_read32(context, 0x8053fff4) == 8;
        titleFlush &= (context.lr == 0x80242fc8 && context.gpr[3] == 0x8053ff40 && address == 0x8053ff20) ||
            (context.lr == 0x80243068 && context.gpr[3] == 0x80540010 && address == 0x53ff20);
    }
"""
changes += "flush_path = output / 'flush_syscall.h'\nreplace(flush_path, '#include \"fpu_first_use.h\"', '#include \"fpu_first_use.h\"\\n#include \"stm_async_dispatch.h\"')\n"
enter = 'inline bool experiment_flush_syscall_enter(CPUContext& context, uint32_t instruction) {\n    auto& state = bat_context(context);'
changes += "replace(flush_path, " + repr(enter) + ", " + repr(enter + '\n' + flush) + ")\n"
changes += """replace(flush_path, '(context.lr != 0x8024262c && (!experimentFlushPacket || context.lr != 0x80242240))',
    '(context.lr != 0x8024262c && (!experimentFlushPacket || context.lr != 0x80242240) && !titleFlush)')
wrapper = output / 'boot-wrapper.cpp'
replace(wrapper, '#include "stm_async_dispatch.h"', '#include "stm_async_dispatch.h"\\n#include "es_title_adapter.h"')
"""
producer = """    if (stmSubmitted == 11) {
        hw::experiment_fixture_reply_after(request, 2, [request](CPUContext& active, uint64_t) {
            experiment_es_title_dispatch(active, request);
            ++stmProduced;
        });
        return;
    }
"""
changes += "replace(wrapper, '    if (stmSubmitted == 5) {', " + repr(producer + '    if (stmSubmitted == 5) {') + ")\n"
changes += "replace(wrapper, 'inline unsigned stmProduced = 0;', 'inline unsigned stmProduced = 0;\\ninline uint32_t experimentTitleCaller = 0;\\ninline bool experimentTitleCaptured = false;')\n"
observe = """    if (address == 0x80249c40 && stmSubmitted == 10 && !experimentTitleCaller) {
        experimentTitleCaller = context.gpr[3];
        std::cout << "BOOT_TITLE_BEFORE " << experimentTitleCaller;
        for (unsigned index = 0; index < 32; ++index) {
            std::cout << ' ' << unsigned(bat_memory_read8(context, experimentTitleCaller + index));
        }
        std::cout << '\\n';
    }
    if (stmSubmitted == 12 && stmProduced == 5 && !experimentTitleCaptured && experimentTitleCaller &&
        (context.msr & 0x10) && bat_memory_read32(context, experimentTitleCaller) != 0 &&
        bat_memory_read32(context, experimentTitleCaller) == bat_memory_read32(context, 0xc053ff20) &&
        bat_memory_read32(context, experimentTitleCaller + 4) == bat_memory_read32(context, 0xc053ff24)) {
        experimentTitleCaptured = true;
        std::cout << "BOOT_TITLE_CAPTURE_AT " << std::hex << address << std::dec << '\\n';
        std::cout << "BOOT_TITLE_AFTER " << experimentTitleCaller;
        for (unsigned index = 0; index < 32; ++index) {
            std::cout << ' ' << unsigned(bat_memory_read8(context, experimentTitleCaller + index));
        }
        std::cout << '\\n';
        for (bool cached : {false, true}) {
            std::cout << (cached ? "BOOT_TITLE_REPLY_CACHED" : "BOOT_TITLE_REPLY_PHYSICAL");
            for (unsigned index = 0; index < 64; ++index) {
                std::cout << ' ' << unsigned(bat_memory_read8(context, 0x135e0080 + index +
                    (cached ? 0x80000000 : 0xc0000000)));
            }
            std::cout << '\\n';
            std::cout << (cached ? "BOOT_TITLE_TEMP_CACHED" : "BOOT_TITLE_TEMP_PHYSICAL");
            for (unsigned index = 0; index < 32; ++index) {
                std::cout << ' ' << unsigned(bat_memory_read8(context, 0x53ff20 + index +
                    (cached ? 0x80000000 : 0xc0000000)));
            }
            std::cout << '\\n';
        }
        std::cout << "BOOT_TITLE_HEAP" << std::hex << ' ' << bat_memory_read32(context, 0x804b2b4c)
            << ' ' << bat_memory_read32(context, 0x935e0004) << std::dec << '\\n';
    }
"""
changes += "replace(wrapper, '    original_trace_call(address, context);', " + repr(observe + '    original_trace_call(address, context);') + ")\n"
changes += "es_source = output / 'es_device.cpp'\n"
changes += "replace(es_source, '#include <stdexcept>', '#include <stdexcept>\\n#include \"es_title_adapter.h\"')\n"
member = """    std::array<uint8_t, 8> title_;
public:
    ESDevice() : title_(experiment_load_es_title(std::getenv("SHSM_ES_TMD_PATH"))) {}
"""
changes += "replace(es_source, 'public:', " + repr(member) + ")\n"
service = """    int32_t ioctlv(CPUContext& context, const IpcRequest& req) override {
        if (req.cmd != 7 || req.fd != 3 || req.req_addr != 0x135e0080 || req.ioctl_cmd != 0x20 ||
            req.arg_cnt_in || req.arg_cnt_out != 1 || req.ioctlv_vecs.size() != 1 ||
            req.ioctlv_vecs[0].len != 8 || req.ioctlv_vecs[0].addr != 0x53ff20) {
            throw std::runtime_error("ES IOCTLV outside verified title profile");
        }
        auto* output = experiment_ipc_mem1_span(context, req.ioctlv_vecs[0].addr, 8);
        std::copy(title_.begin(), title_.end(), output);
        return IPC_OK;
    }
"""
old = """    int32_t ioctlv(CPUContext&, const IpcRequest&) override {
        throw std::runtime_error("ES IOCTLV unverified");
    }
"""
changes += "replace(es_source, " + repr(old) + ", " + repr(service) + ")\n"
changes += "fs_source = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime/src/hle/devices/es_device.cpp')\n"
body = body[:start] + changes + body[end:]
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp'")
body = body.replace("for name in ('output_62.cpp', 'output_67.cpp'):", "for name in ('output_62.cpp', 'output_63.cpp', 'output_67.cpp'):")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_ES_TITLE_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'\n    result = subprocess.run([str(exe),")
body = body.replace("'BOOT_FS_REPLY', 'BOOT_STM_ASYNC", "'BOOT_FS_REPLY', 'BOOT_ES_REPLY', 'BOOT_STM_ASYNC")
body = body.replace("'vendorFsSha256': sha(fs_source)", "'vendorEsSha256': sha(fs_source)")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-es-title-boot')
report = json.loads((output / 'build.json').read_text())
report['parentBuilderSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['adapterSha256'] = hashlib.sha256((experiment / 'es_title_adapter.h').read_bytes()).hexdigest()
report['tmdSha256'] = hashlib.sha256(Path('work/private-game/disc/DATA/tmd.bin').read_bytes()).hexdigest()
report['limits'] = ['Exactly first title IOCTLV and its two measured EE flush sites; actual existing device/kernel writes only output8 from own TMD.',
    'No other ES command/result, arbitrary vectors, credentials, pending-STM completion, timing or gameplay proof.']
(output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')

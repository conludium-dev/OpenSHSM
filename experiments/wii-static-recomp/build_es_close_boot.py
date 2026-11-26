"""Integrate only the verified first ES CLOSE into the existing native boot."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-es-datadir-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-es-close-boot'")
body = body.replace("('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_es_datadir_boot.py', 'verify_es_close_disc.py')")
body = body.replace("'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'boot-quarantine.tsv'")
start = body.index("packet = output / 'ipc_open_packet.h'")
end = body.index('records = [dict(row)', start)
changes = '''
(output / 'es_close_adapter.h').write_bytes((experiment / 'es_close_adapter.h').read_bytes())
front = output / 'ipc_ack_frontend.h'
replace(front, '|| stmSubmitted == 13)', '|| stmSubmitted == 13 || stmSubmitted == 15)', 2)
replace(front, '(stmSubmitted == 12 && !std::getenv("SHSM_ES_DATADIR_DISABLED")))',
    '(stmSubmitted == 12 && !std::getenv("SHSM_ES_DATADIR_DISABLED")) || (stmSubmitted == 14 && !std::getenv("SHSM_ES_CLOSE_DISABLED")))')
'''
admission = '''            if (stmSubmitted == 14) {
                const auto* packet = context.mmu.get_ptr(value);
                const std::array<uint32_t, 8> expected{2, 0, 3, 0x1d, 1, 1, 0x80540010, 0};
                if (value != 0x135e0080 || !devices::experiment_stm_pending()) {
                    throw std::runtime_error("ES CLOSE sender/pending owner unverified");
                }
                for (unsigned index = 0; index < expected.size(); ++index) {
                    if (experiment_ipc_be32(packet + index * 4) != expected[index]) {
                        throw std::runtime_error("ES CLOSE sender physical header unverified");
                    }
                }
            }
'''
changes += "replace(front, '            if (stmSubmitted == 4) {', " + repr(admission + '            if (stmSubmitted == 4) {') + ")\n"
changes += '''wrapper = output / 'boot-wrapper.cpp'
replace(wrapper, '#include "es_datadir_adapter.h"', '#include "es_datadir_adapter.h"\\n#include "es_close_adapter.h"')
replace(wrapper, 'inline bool experimentDataDirCaptured = false;', 'inline bool experimentDataDirCaptured = false;\\ninline bool experimentCloseCaptured = false;')
'''
producer = '''    if (stmSubmitted == 15) {
        hw::experiment_fixture_reply_after(request, 2, [request](CPUContext& active, uint64_t) {
            experiment_es_close_dispatch(active, request);
            ++stmProduced;
        });
        return;
    }
'''
changes += "replace(wrapper, '    if (stmSubmitted == 13) {', " + repr(producer + '    if (stmSubmitted == 13) {') + ")\n"
observe = '''    if (stmSubmitted == 16 && stmProduced == 7 && !experimentCloseCaptured && (context.msr & 0x10) &&
        bat_memory_read32(context, 0x80528ce8) == 0xffffffff) {
        experimentCloseCaptured = true;
        std::cout << "BOOT_ES_CLOSE_AT" << std::hex << ' ' << address << ' ' << context.lr << std::dec << '\\n';
        std::cout << "BOOT_ES_CLOSE_STATE" << std::hex << ' ' << bat_memory_read32(context, 0x80528ce8)
            << ' ' << bat_memory_read32(context, 0x804b2b4c) << ' ' << bat_memory_read32(context, 0x935e0004)
            << std::dec << '\\n';
        for (bool cached : {false, true}) {
            std::cout << (cached ? "BOOT_ES_CLOSE_CACHED" : "BOOT_ES_CLOSE_PHYSICAL");
            for (unsigned index = 0; index < 64; ++index) {
                std::cout << ' ' << unsigned(bat_memory_read8(context, 0x135e0080 + index +
                    (cached ? 0x80000000 : 0xc0000000)));
            }
            std::cout << '\\n';
        }
    }
    if (address == 0x80211d10 && context.lr == 0x80246394 && experimentCloseCaptured) {
        std::cout << "BOOT_NAND_INIT_STATE" << std::hex << ' ' << bat_memory_read32(context, 0x8052aff8)
            << std::dec << '\\n';
    }
    if (address == 0x80242430 && stmSubmitted == 16 && stmProduced == 7) {
        std::cout << "BOOT_NEXT_OPEN_ASYNC_ARGS" << std::hex << ' ' << context.gpr[3] << ' ' << context.gpr[4]
            << ' ' << context.gpr[5] << ' ' << context.gpr[6] << std::dec << '\\n';
        std::cout << "BOOT_NEXT_OPEN_ASYNC_PATH";
        for (unsigned index = 0; index < 64; ++index) {
            std::cout << ' ' << unsigned(bat_memory_read8(context, context.gpr[3] + index));
        }
        std::cout << '\\n';
    }
'''
changes += "replace(wrapper, '    original_trace_call(address, context);', " + repr(observe + '    original_trace_call(address, context);') + ")\n"
changes += "fs_source = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime/src/hle/devices/es_device.cpp')\n"
body = body[:start] + changes + body[end:]
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp'")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_ES_CLOSE_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'\n    result = subprocess.run([str(exe),")
body = body.replace("'vendorFsSha256': sha(fs_source)", "'vendorEsSha256': sha(fs_source)")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-es-close-boot')
report = json.loads((output / 'build.json').read_text())
report['parentBuilderSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['adapterSha256'] = hashlib.sha256((experiment / 'es_close_adapter.h').read_bytes()).hexdigest()
report['limits'] = ['Exactly first ES FD3 CLOSE with unchanged existing device/kernel and reused ignored packet fields.',
    'Original SDK stores FD-1; no forced descriptor, other CLOSE, pending-STM completion, file/save IO, timing or gameplay proof.']
(output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')

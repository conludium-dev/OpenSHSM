"""Submit the measured READ128 with original callback/allocator ordering preserved."""
from pathlib import Path
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-fp-initializer-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-playrecord-read-boot'").replace(
    "('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_fp_initializer_boot.py', 'verify_playrecord_fs_device.py')").replace(
    "'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'di_device.cpp', 'boot-quarantine.tsv'")
start,end = body.index("packet = output / 'ipc_open_packet.h'"),body.index('records = [dict(row)')
changes = '''
front = output / 'ipc_ack_frontend.h'
wrapper = output / 'boot-wrapper.cpp'
(output / 'playrecord_read_dispatch.h').write_bytes((experiment / 'playrecord_read_dispatch.h').read_bytes())
(output / 'playrecord_read_flush.h').write_bytes((experiment / 'playrecord_read_flush.h').read_bytes())
replace(front, '#include "playrecord_open_dispatch.h"', '#include "playrecord_open_dispatch.h"\\n#include "playrecord_read_dispatch.h"')
flush = output / 'flush_syscall.h'
replace(flush, '#include "playrecord_open_flush.h"', '#include "playrecord_open_flush.h"\\n#include "playrecord_read_flush.h"')
replace(flush, '    bool nestedRead =', '    bool playrecordRead = experiment_playrecord_read_flush(context);\\n    bool nestedRead =')
replace(flush, '&& !nestedRead && !nestedClose', '&& !playrecordRead && !nestedRead && !nestedClose')
replace(flush, 'experimentFlushCallback = nestedRead ||', 'experimentFlushCallback = playrecordRead || nestedRead ||')
replace(front, '    if (experiment_es_consumption_prior_arm(message, arm))', '    if (experiment_playrecord_read_prior_arm(message, arm)) { return true; }\\n    if (experiment_es_consumption_prior_arm(message, arm))')
replace(front, '|| stmSubmitted == 43)', '|| stmSubmitted == 43 || stmSubmitted == 45)', 2)
replace(front, '|| stmSubmitted == 27))) &&', '|| stmSubmitted == 27 || stmSubmitted == 45))) &&')
replace(front, '(stmSubmitted >= 18 && stmSubmitted <= 27)', '((stmSubmitted >= 18 && stmSubmitted <= 27) || stmSubmitted == 44 || stmSubmitted == 45)')
replace(front, '|| stmSubmitted == 44)', '|| stmSubmitted == 44 || stmSubmitted == 46)', front.read_text().count('|| stmSubmitted == 44)'))
replace(front, '(stmSubmitted == 42 && !std::getenv("SHSM_PLAYRECORD_OPEN_DISABLED")))', '(stmSubmitted == 42 && !std::getenv("SHSM_PLAYRECORD_OPEN_DISABLED")) || (stmSubmitted == 44 && !std::getenv("SHSM_PLAYRECORD_READ_DISABLED")))')
replace(front, '(stmSubmitted == 36 && state.ppcMessage == 0x135e0140 && value == 0x135e0080)) &&', '(stmSubmitted == 36 && state.ppcMessage == 0x135e0140 && value == 0x135e0080) || (stmSubmitted == 44 && state.ppcMessage == 0x135e0080 && value == 0x135e00e0)) &&')
replace(front, '            if (stmSubmitted == 42) {', '            if (stmSubmitted == 44) {\\n                experiment_playrecord_read_validate(context,value);\\n            }\\n            if (stmSubmitted == 42) {')
replace(front, 'experiment_playrecord_open_ready(', 'experiment_playrecord_read_ready(', front.read_text().count('experiment_playrecord_open_ready('))
replace(front, '    hw::experiment_ipc_control_latched_irq(value);', '    experiment_playrecord_open_retire(context,value,final);\\n    hw::experiment_ipc_control_latched_irq(value);')
si = output / 'si_external_delivery.h'
replace(si, '|| stmSubmitted == 44)', '|| stmSubmitted == 44 || stmSubmitted == 46)', 2)
replace(si, 'experiment_playrecord_open_ready(', 'experiment_playrecord_read_ready(', si.read_text().count('experiment_playrecord_open_ready('))
poll = """void experiment_playrecord_read_poll(CPUContext&,uint64_t) {
    if (!experimentPlayrecordOpenRetired) {
        EventScheduler::get().schedule_after(1,experiment_playrecord_read_poll);
        return;
    }
    hw::experiment_fixture_reply_after(0x135e00e0,1,[](CPUContext& active,uint64_t) {
        experiment_playrecord_read_dispatch(active,0x135e00e0);
        ++stmProduced;
    });
}
"""
replace(wrapper, 'void experiment_stm_submit(CPUContext& context, uint32_t request) {', poll + 'void experiment_stm_submit(CPUContext& context, uint32_t request) {')
replace(wrapper, '    if (stmSubmitted == 43) {', '    if (stmSubmitted == 45) {\\n        if (request != 0x135e00e0) { throw std::runtime_error("Play-record READ sender owner unverified"); }\\n        hw::ipc_ppc_ctrl = 0x30;\\n        EventScheduler::get().schedule_after(64,[](CPUContext&,uint64_t) { hw::ipc_ppc_ctrl = (hw::ipc_ppc_ctrl & ~1u) | 2; });\\n        EventScheduler::get().schedule_after(65,experiment_playrecord_read_poll);\\n        return;\\n    }\\n    if (stmSubmitted == 43) {')
replace(wrapper, '    if (stmSubmitted == 45) {', '    if (stmSubmitted == 45) {\\n        std::cout << "PLAYRECORD_READ_SUBMITTED" << std::endl;')
entry = output / 'mass_boot.cpp'
observer = """        if (nwii::runtime::stmSubmitted == 46) {
            std::cout << "PLAYRECORD_NEXT_STATE " << std::hex << context.gpr[3] << ' ' << context.gpr[4] << ' '
                << nwii::runtime::bat_memory_read32(context,0x80528a40) << ' ' << nwii::runtime::bat_memory_read32(context,0x8052ab40) << ' '
                << nwii::runtime::bat_memory_read32(context,0x804931d0) << ' ' << nwii::runtime::bat_memory_read32(context,0x804b2b4c) << std::dec << std::endl;
            for (bool cached : {false,true}) {
                std::cout << (cached ? "PLAYRECORD_NEXT_CACHED" : "PLAYRECORD_NEXT_PHYSICAL");
                for (unsigned index = 0; index < 64; ++index) { std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context,(cached ? 0x935e0080u : 0xd35e0080u) + index)); }
                std::cout << std::endl;
            }
        }
"""
replace(entry, '        std::cout << "BOOT_ES_LAYOUT "', observer + '        std::cout << "BOOT_ES_LAYOUT "')
fs_source = runtime / 'src/hle/devices/fs_device.cpp'
'''
body = body[:start] + changes + body[end:]
body = body.replace("('output_62.cpp', 'output_67.cpp')", "('output_62.cpp', 'output_63.cpp', 'output_64.cpp', 'output_67.cpp', 'output_68.cpp')")
body = body.replace("    source.write_bytes(Path(row['source']).read_bytes())", "    source.write_bytes(Path(row['source']).read_bytes())\n    if name == 'output_67.cpp':\n        replace(source,'loc_80240680: ;','loc_80240680: ;\\n    nwii::runtime::experiment_playrecord_read_observe(ctx,1);')\n    if name == 'output_64.cpp':\n        label = 'loc_8021CDE0: ;'\n        replace(source,label,label + '\\n    nwii::runtime::experiment_playrecord_read_observe(ctx,2);',source.read_text().count(label))")
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp', output / 'di_device.cpp'")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_PLAYRECORD_READ_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env.update(SHSM_PLAYRECORD_LAB_FILE='work/private-game/static-recomp/playrecord-fs-device/pc-owned-playrecord.bin',SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin',SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin',SHSM_ES_LAB_CONSUMPTION='1',SHSM_DI_LAB_INQUIRY_PATH='work/private-game/static-recomp/di-inquiry-device/dolphin-lab-inquiry.bin',SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF',SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')\n    result = subprocess.run([str(exe),")
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
path = Path('work/private-game/static-recomp/mass-playrecord-read-boot/build.json')
report = json.loads(path.read_text())
report['limits'] = ['Real existing kernel/FS READ128; original callbacks/allocator execute, no forced SDK result.',
    'ACK64 and reply after measured OPEN retirement are PC timing adaptations, not physical IOS timing.',
    'Original READ/SEEK/allocator endpoints require fresh audit; not first screen.']
path.write_text(json.dumps(report,indent=2) + '\n')

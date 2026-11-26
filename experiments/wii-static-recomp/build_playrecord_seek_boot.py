"""Execute exact SEEK0 through the existing kernel after source READ retirement."""
from pathlib import Path
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-playrecord-read-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-playrecord-seek-boot'").replace(
    "('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_playrecord_read_boot.py', 'verify_playrecord_fs_device.py')").replace(
    "'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'di_device.cpp', 'boot-quarantine.tsv'")
start,end = body.index("packet = output / 'ipc_open_packet.h'"),body.index('records = [dict(row)')
changes = '''
front = output / 'ipc_ack_frontend.h'
wrapper = output / 'boot-wrapper.cpp'
for name in ('playrecord_seek_flush.h','playrecord_seek_dispatch.h'):
    (output / name).write_bytes((experiment / name).read_bytes())
replace(front, '#include "playrecord_read_dispatch.h"', '#include "playrecord_read_dispatch.h"\\n#include "playrecord_seek_dispatch.h"')
flush = output / 'flush_syscall.h'
replace(flush, '#include "playrecord_read_flush.h"', '#include "playrecord_read_flush.h"\\n#include "playrecord_seek_flush.h"')
replace(flush, '    bool playrecordRead =', '    bool playrecordSeek = experiment_playrecord_seek_flush(context);\\n    bool playrecordRead =')
replace(flush, '&& !playrecordRead && !nestedRead', '&& !playrecordSeek && !playrecordRead && !nestedRead')
replace(flush, 'experimentFlushCallback = playrecordRead ||', 'experimentFlushCallback = playrecordSeek || playrecordRead ||')
replace(front, '    if (experiment_playrecord_read_prior_arm(message, arm))', '    if (experiment_playrecord_seek_prior_arm(message, arm)) { return true; }\\n    if (experiment_playrecord_read_prior_arm(message, arm))')
replace(front, '|| stmSubmitted == 27 || stmSubmitted == 45))) &&', '|| stmSubmitted == 27 || stmSubmitted == 45 || stmSubmitted == 47))) &&')
replace(front, '|| stmSubmitted == 44 || stmSubmitted == 45)', '|| stmSubmitted == 44 || stmSubmitted == 45 || stmSubmitted == 46 || stmSubmitted == 47)')
replace(front, '|| stmSubmitted == 45)', '|| stmSubmitted == 45 || stmSubmitted == 47)', 2)
replace(front, '|| stmSubmitted == 46)', '|| stmSubmitted == 46 || stmSubmitted == 48)', front.read_text().count('|| stmSubmitted == 46)'))
replace(front, '(stmSubmitted == 44 && !std::getenv("SHSM_PLAYRECORD_READ_DISABLED")))', '(stmSubmitted == 44 && !std::getenv("SHSM_PLAYRECORD_READ_DISABLED")) || (stmSubmitted == 46 && !std::getenv("SHSM_PLAYRECORD_SEEK_DISABLED")))')
replace(front, '(stmSubmitted == 44 && state.ppcMessage == 0x135e0080 && value == 0x135e00e0)) &&', '(stmSubmitted == 44 && state.ppcMessage == 0x135e0080 && value == 0x135e00e0) || (stmSubmitted == 46 && state.ppcMessage == 0x135e00e0 && value == 0x135e0080)) &&')
replace(front, '            if (stmSubmitted == 44) {', '            if (stmSubmitted == 46) {\\n                experiment_playrecord_seek_validate(context,value);\\n            }\\n            if (stmSubmitted == 44) {')
replace(front, 'experiment_playrecord_read_ready(', 'experiment_playrecord_seek_ready(', front.read_text().count('experiment_playrecord_read_ready('))
replace(front, '    experiment_playrecord_open_retire(context,value,final);', '    experiment_playrecord_open_retire(context,value,final);\\n    experiment_playrecord_seek_retire(context,value,final);')
si = output / 'si_external_delivery.h'
replace(si, '|| stmSubmitted == 46)', '|| stmSubmitted == 46 || stmSubmitted == 48)', 2)
replace(si, 'experiment_playrecord_read_ready(', 'experiment_playrecord_seek_ready(', si.read_text().count('experiment_playrecord_read_ready('))
poll = """void experiment_playrecord_seek_poll(CPUContext&,uint64_t) {
    if (!experimentPlayrecordReadRetired) {
        EventScheduler::get().schedule_after(1,experiment_playrecord_seek_poll);
        return;
    }
    hw::experiment_fixture_reply_after(0x135e0080,1,[](CPUContext& active,uint64_t) {
        experiment_playrecord_seek_dispatch(active,0x135e0080);
        ++stmProduced;
    });
}
"""
replace(wrapper, 'void experiment_stm_submit(CPUContext& context, uint32_t request) {', poll + 'void experiment_stm_submit(CPUContext& context, uint32_t request) {')
replace(wrapper, '    if (stmSubmitted == 45) {', '    if (stmSubmitted == 47) {\\n        if (request != 0x135e0080) { throw std::runtime_error("Play-record SEEK sender owner unverified"); }\\n        std::cout << "PLAYRECORD_SEEK_SUBMITTED" << std::endl;\\n        hw::ipc_ppc_ctrl = 0x30;\\n        EventScheduler::get().schedule_after(64,[](CPUContext&,uint64_t) { hw::ipc_ppc_ctrl = (hw::ipc_ppc_ctrl & ~1u) | 2; });\\n        EventScheduler::get().schedule_after(65,experiment_playrecord_seek_poll);\\n        return;\\n    }\\n    if (stmSubmitted == 45) {')
entry = output / 'mass_boot.cpp'
observer = """        if (nwii::runtime::stmSubmitted == 48) {
            std::cout << "PLAYRECORD_SEEK_END_STATE " << std::hex;
            for (uint32_t address : {0x80528a40u,0x8052ab40u,0x8052ab44u,0x8052ab48u,0x8052ab4cu,0x8052ab50u,0x8052ab54u,0x804931d0u,0x804b2b4cu}) { std::cout << ' ' << nwii::runtime::bat_memory_read32(context,address); }
            std::cout << std::dec << std::endl;
        }
"""
replace(entry, '        std::cout << "BOOT_ES_LAYOUT "', observer + '        std::cout << "BOOT_ES_LAYOUT "')
fs_source = runtime / 'src/hle/devices/fs_device.cpp'
'''
body = body[:start] + changes + body[end:]
body = body.replace("('output_62.cpp', 'output_67.cpp')", "('output_62.cpp', 'output_63.cpp', 'output_64.cpp', 'output_67.cpp', 'output_68.cpp')")
body = body.replace("    source.write_bytes(Path(row['source']).read_bytes())", "    source.write_bytes(Path(row['source']).read_bytes())\n    if name == 'output_67.cpp':\n        for label,kind in [('loc_80240680: ;',1),('loc_802407D0: ;',3),('loc_802438B0: ;',4)]:\n            replace(source,label,label + '\\n    nwii::runtime::experiment_playrecord_seek_observe(ctx,' + str(kind) + ');')\n    if name == 'output_64.cpp':\n        label = 'loc_8021CDE0: ;'\n        replace(source,label,label + '\\n    nwii::runtime::experiment_playrecord_seek_observe(ctx,2);',source.read_text().count(label))")
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp', output / 'di_device.cpp'")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_PLAYRECORD_SEEK_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env.update(SHSM_PLAYRECORD_LAB_FILE='work/private-game/static-recomp/playrecord-fs-device/pc-owned-playrecord.bin',SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin',SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin',SHSM_ES_LAB_CONSUMPTION='1',SHSM_DI_LAB_INQUIRY_PATH='work/private-game/static-recomp/di-inquiry-device/dolphin-lab-inquiry.bin',SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF',SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')\n    result = subprocess.run([str(exe),")
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
path = Path('work/private-game/static-recomp/mass-playrecord-seek-boot/build.json')
report = json.loads(path.read_text())
report['limits'] = ['Existing kernel/FS seek0 after source READ retirement; original callbacks/allocator/state execute.',
    'ACK64/reply poll after source retirement is PC timing; complete source state/free requires fresh audit.',
    'No WRITE/CLOSE/physical Wii/first screen claim.']
path.write_text(json.dumps(report,indent=2) + '\n')

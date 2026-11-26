"""Deliver only measured pending inquiry after genuine ticket return, no forced callbacks."""
from pathlib import Path
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-es-di-ticket-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-di-inquiry-boot'").replace(
    "('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_es_di_ticket_boot.py', 'verify_di_inquiry_device.py')").replace(
    "'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'di_device.cpp', 'boot-quarantine.tsv'")
start, end = body.index("packet = output / 'ipc_open_packet.h'"), body.index('records = [dict(row)')
changes = '''
front = output / 'ipc_ack_frontend.h'
wrapper = output / 'boot-wrapper.cpp'
(output / 'di_inquiry_adapter.h').write_bytes((experiment / 'di_inquiry_adapter.h').read_bytes())
(output / 'di_inquiry_runtime.h').write_bytes((experiment / 'di_inquiry_runtime.h').read_bytes())
(output / 'di_device.cpp').write_bytes(Path('work/private-game/static-recomp/di-inquiry-device/di_device.cpp').read_bytes())
replace(front, '#include "es_di_ticket_dispatch.h"', '#include "es_di_ticket_dispatch.h"\\n#include "di_inquiry_runtime.h"')
replace(front, 'experiment_di_burst_reply_ready(ipc)', 'experiment_inquiry_reply_ready(ipc)', 3)
replace(front, 'experiment_di_burst_arm_match(ipc.ppcMessage, ipc.armMessage)',
    '(experiment_di_burst_arm_match(ipc.ppcMessage, ipc.armMessage) || experiment_inquiry_arm(ipc.ppcMessage, ipc.armMessage))',
    front.read_text().count('experiment_di_burst_arm_match(ipc.ppcMessage, ipc.armMessage)'))
replace(front, 'inline bool experiment_fs_prior_arm(uint32_t message, uint32_t arm) {',
    'inline bool experiment_fs_prior_arm(uint32_t message, uint32_t arm) {\\n    if (experiment_inquiry_arm(message, arm)) { return true; }')
si = output / 'si_external_delivery.h'
replace(si, 'experiment_di_burst_reply_ready(', 'experiment_inquiry_reply_ready(', si.read_text().count('experiment_di_burst_reply_ready('))
replace(wrapper, 'void experiment_stm_submit(CPUContext& context, uint32_t request) {',
    (experiment / 'di_inquiry_poll.inc').read_text() + '\\nvoid experiment_stm_submit(CPUContext& context, uint32_t request) {')
replace(wrapper, '    if (stmSubmitted == 37) {',
    '    if (stmSubmitted == 37) {\\n        if (!std::getenv("SHSM_DI_INQUIRY_DISABLED")) { EventScheduler::get().schedule_after(1, experiment_inquiry_poll); }')
replace(wrapper, '    original_trace_call(address, context);',
    '    if (address == 0x802438b0 && stmSubmitted == 38 && experimentInquiryReplyActive) {\\n        std::cout << "INQUIRY_SOURCE_FREE " << std::hex << context.gpr[3] << \\' \\' << context.gpr[4] << \\' \\' << context.msr << \\' \\' << bat_memory_read32(context, 0x804983c8) << std::dec << std::endl;\\n    }\\n    original_trace_call(address, context);')
fs_source = runtime / 'src/hle/devices/fs_device.cpp'
'''
body = body[:start] + changes + body[end:]
body = body.replace("('output_62.cpp', 'output_67.cpp')", "('output_62.cpp', 'output_63.cpp', 'output_64.cpp', 'output_65.cpp', 'output_67.cpp', 'output_68.cpp')")
addition = """
    if name == 'output_63.cpp':
        replace(source, 'nwii::runtime::experiment_di_burst_cache_operation(ctx, ctx.gpr[3], 470);', 'nwii::runtime::experiment_inquiry_cache_operation(ctx, ctx.gpr[3], 470);')
        replace(source, 'loc_80211060: ;', 'loc_80211060: ;\\n    nwii::runtime::experiment_inquiry_observe(ctx, 3);')
    if name == 'output_64.cpp':
        replace(source, 'loc_80222F80: ;', 'loc_80222F80: ;\\n    nwii::runtime::experiment_inquiry_observe(ctx, 2);')
    if name == 'output_65.cpp':
        for label, kind in [('loc_802258A0: ;', 1), ('loc_80225940: ;', 4)]:
            replace(source, label, label + '\\n    nwii::runtime::experiment_inquiry_observe(ctx, ' + str(kind) + ');')
    if name == 'output_68.cpp':
        replace(source, 'nwii::runtime::experiment_es_ticket_observe(ctx, 2);', 'nwii::runtime::experiment_es_ticket_observe(ctx, 2);\\n    nwii::runtime::experiment_inquiry_ticket_return(ctx);')
"""
body = body.replace("    source.write_bytes(Path(row['source']).read_bytes())", "    source.write_bytes(Path(row['source']).read_bytes())\n" + addition)
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp', output / 'di_device.cpp'")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_DI_INQUIRY_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'\n    env['SHSM_ES_TICKET_PATH'] = 'work/private-game/disc/DATA/ticket.bin'\n    env['SHSM_DI_LAB_INQUIRY_PATH'] = 'work/private-game/static-recomp/di-inquiry-device/dolphin-lab-inquiry.bin'\n    env['SHSM_SC_LAB_FILE'] = '_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF'\n    env['SHSM_SC_LAB_PRODUCT'] = '_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt'\n    result = subprocess.run([str(exe),")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-di-inquiry-boot')
report = json.loads((output / 'build.json').read_text())
report['limits'] = ['Existing DI/kernel/event inquiry delivery gated by actual ticket SDK return and free, not manual callback invocation.',
    'LAB drive metadata and observed input-dcbi no-op are explicit PC experiment adaptations, not physical Wii identity/cycles.',
    'Six objects rebuilt/119 retained; source63 cache binding/observers,64-65 observers,68 readiness bookkeeping; completion requires audit.']
(output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')

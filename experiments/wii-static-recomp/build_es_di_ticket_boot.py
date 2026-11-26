"""Complete exactly measured native1B through existing sender/kernel/events."""
from pathlib import Path
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-es-di-ticket-flush-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-es-di-ticket-boot'").replace(
    "('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_es_di_ticket_flush_boot.py', 'verify_es_di_ticket_events_dolphin.py')").replace(
    "'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'di_device.cpp', 'boot-quarantine.tsv'")
start, end = body.index("packet = output / 'ipc_open_packet.h'"), body.index('records = [dict(row)')
changes = '''
front = output / 'ipc_ack_frontend.h'
wrapper = output / 'boot-wrapper.cpp'
(output / 'es_di_ticket_dispatch.h').write_bytes((experiment / 'es_di_ticket_dispatch.h').read_bytes())
replace(front, '#include "di_burst_cache_adapter.h"', '#include "di_burst_cache_adapter.h"\\n#include "es_di_ticket_dispatch.h"')
replace(front, '|| stmSubmitted == 31)', '|| stmSubmitted == 31 || stmSubmitted == 37)', 2)
replace(front, '|| stmSubmitted == 36)', '|| stmSubmitted == 36 || stmSubmitted == 38)', front.read_text().count('|| stmSubmitted == 36)'))
replace(front, 'inline bool experiment_fs_prior_arm(uint32_t message, uint32_t arm) {',
    'inline bool experiment_fs_prior_arm(uint32_t message, uint32_t arm) {\\n    if ((stmSubmitted == 37 || stmSubmitted == 38) && message == 0x135e0080 && arm == 0x135e0140 && experimentDiBurstFirstRetired) { return true; }')
replace(front, '(stmSubmitted == 30 && !std::getenv("SHSM_DI86_DISABLED")))',
    '(stmSubmitted == 30 && !std::getenv("SHSM_DI86_DISABLED")) || (stmSubmitted == 36 && !std::getenv("SHSM_ES_DI_TICKET_DISABLED")))')
replace(front, '&& value == 0x135e0080)) &&', '&& value == 0x135e0080) || (stmSubmitted == 36 && state.ppcMessage == 0x135e0140 && value == 0x135e0080)) &&')
replace(front, '            if (stmSubmitted == 30) {',
    '            if (stmSubmitted == 36) {\\n                experiment_es_ticket_validate(context, value);\\n            }\\n            if (stmSubmitted == 30) {')
replace(output / 'si_external_delivery.h', '|| stmSubmitted == 36)', '|| stmSubmitted == 36 || stmSubmitted == 38)', 2)
replace(wrapper, '    if (stmSubmitted == 31) {', '    if (stmSubmitted == 37) {\\n        hw::ipc_ppc_ctrl = 0x31;\\n        EventScheduler::get().schedule_after(64, [](CPUContext&, uint64_t) {\\n            hw::ipc_ppc_ctrl = (hw::ipc_ppc_ctrl & ~1u) | 2;\\n        });\\n        hw::experiment_fixture_reply_after(request, 65, [request](CPUContext& active, uint64_t) {\\n            experiment_es_ticket_dispatch(active, request);\\n            ++stmProduced;\\n        });\\n        return;\\n    }\\n    if (stmSubmitted == 31) {')
fs_source = runtime / 'src/hle/devices/fs_device.cpp'
'''
body = body[:start] + changes + body[end:]
body = body.replace("('output_62.cpp', 'output_67.cpp')", "('output_62.cpp', 'output_67.cpp', 'output_68.cpp')")
body = body.replace("    source.write_bytes(Path(row['source']).read_bytes())", "    source.write_bytes(Path(row['source']).read_bytes())\n    if name == 'output_68.cpp':\n        for label, kind in [('loc_80249A00: ;', 1), ('loc_80249A90: ;', 2)]:\n            replace(source, label, label + '\\n    nwii::runtime::experiment_es_ticket_observe(ctx, ' + str(kind) + ');')")
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp', output / 'di_device.cpp'")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_ES_DI_TICKET_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'\n    env['SHSM_ES_TICKET_PATH'] = 'work/private-game/disc/DATA/ticket.bin'\n    env['SHSM_SC_LAB_FILE'] = '_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF'\n    env['SHSM_SC_LAB_PRODUCT'] = '_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt'\n    result = subprocess.run([str(exe),")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-es-di-ticket-boot')
report = json.loads((output / 'build.json').read_text())
report['limits'] = ['Exactly measured1B shared-kernel response; old incomplete inquiry preserved until separate verified delivery.',
    'Original wrapper return/caller216 bytes/free order require audit. ACK64/reply65 are PC timing adaptation.']
(output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')

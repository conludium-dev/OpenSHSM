"""Close exact real ES FD4 through existing kernel/events, preserving old CLOSE tools."""
from pathlib import Path
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-es-consumption-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-es-close-after-consumption-boot'").replace(
    "('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_es_consumption_boot.py', 'verify_post_es_consumption.py', 'verify_es_close_after_consumption_dolphin.py')").replace(
    "'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'di_device.cpp', 'boot-quarantine.tsv'")
start, end = body.index("packet = output / 'ipc_open_packet.h'"), body.index('records = [dict(row)')
changes = '''
front = output / 'ipc_ack_frontend.h'
wrapper = output / 'boot-wrapper.cpp'
(output / 'es_close_after_consumption_adapter.h').write_bytes((experiment / 'es_close_after_consumption_adapter.h').read_bytes())
replace(front, '#include "es_consumption_dispatch.h"', '#include "es_consumption_dispatch.h"\\n#include "es_close_after_consumption_adapter.h"')
replace(front, '|| stmSubmitted == 39)', '|| stmSubmitted == 39 || stmSubmitted == 41)', 2)
replace(front, '|| stmSubmitted == 40)', '|| stmSubmitted == 40 || stmSubmitted == 42)', front.read_text().count('|| stmSubmitted == 40)'))
replace(front, 'if ((stmSubmitted == 37 || stmSubmitted == 38 || stmSubmitted == 40 || stmSubmitted == 42) &&',
    'if ((stmSubmitted == 37 || stmSubmitted == 38 || stmSubmitted == 40) &&')
replace(front, '(stmSubmitted == 38 && !std::getenv("SHSM_ES_CONSUMPTION_DISABLED")))',
    '(stmSubmitted == 38 && !std::getenv("SHSM_ES_CONSUMPTION_DISABLED")) || (stmSubmitted == 40 && !std::getenv("SHSM_POST_ES16_CLOSE_DISABLED")))')
replace(front, '            if (stmSubmitted == 38) {',
    '            if (stmSubmitted == 40) {\\n                experiment_post_consumption_close_validate(context, value);\\n            }\\n            if (stmSubmitted == 38) {')
replace(front, 'experiment_es_consumption_reply_ready(ipc)', 'experiment_post_consumption_close_ready(ipc)', front.read_text().count('experiment_es_consumption_reply_ready(ipc)'))
si = output / 'si_external_delivery.h'
replace(si, '|| stmSubmitted == 40)', '|| stmSubmitted == 40 || stmSubmitted == 42)', 2)
replace(si, 'experiment_es_consumption_reply_ready(', 'experiment_post_consumption_close_ready(', si.read_text().count('experiment_es_consumption_reply_ready('))
replace(wrapper, '    if (stmSubmitted == 39) {',
    '    if (stmSubmitted == 41) {\\n        hw::ipc_ppc_ctrl = 0x31;\\n        EventScheduler::get().schedule_after(64, [](CPUContext&, uint64_t) {\\n            hw::ipc_ppc_ctrl = (hw::ipc_ppc_ctrl & ~1u) | 2;\\n        });\\n        hw::experiment_fixture_reply_after(request, 65, [request](CPUContext& active, uint64_t) {\\n            experiment_post_consumption_close_dispatch(active, request);\\n            ++stmProduced;\\n        });\\n        return;\\n    }\\n    if (stmSubmitted == 39) {')
fs_source = runtime / 'src/hle/devices/fs_device.cpp'
'''
body = body[:start] + changes + body[end:]
body = body.replace("('output_62.cpp', 'output_67.cpp')", "('output_62.cpp', 'output_67.cpp', 'output_68.cpp')")
body = body.replace("    source.write_bytes(Path(row['source']).read_bytes())", "    source.write_bytes(Path(row['source']).read_bytes())\n    if name == 'output_68.cpp':\n        for label, kind in [('loc_802497F0: ;', 1), ('loc_80249834: ;', 2)]:\n            replace(source, label, label + '\\n    nwii::runtime::experiment_post_consumption_close_observe(ctx, ' + str(kind) + ');')")
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp', output / 'di_device.cpp'")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_POST_ES16_CLOSE_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env.update(SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin', SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin', SHSM_ES_LAB_CONSUMPTION='1', SHSM_DI_LAB_INQUIRY_PATH='work/private-game/static-recomp/di-inquiry-device/dolphin-lab-inquiry.bin', SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF', SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')\n    result = subprocess.run([str(exe),")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-es-close-after-consumption-boot')
report = json.loads((output / 'build.json').read_text())
report['limits'] = ['Actual existing kernel.close FD4; original SDK clears its descriptor and frees packet.',
    'Only exact post-ES16 CLOSE admitted; ACK64/reply65 PC timing; native return/lifecycle require audit.']
(output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')

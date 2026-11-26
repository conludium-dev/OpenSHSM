"""Submit measured play-record OPEN through the existing kernel and event path."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-playrecord-open-flush-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-playrecord-open-boot'").replace(
    "('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_playrecord_open_flush_boot.py', 'verify_playrecord_fs_device.py')").replace(
    "'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'di_device.cpp', 'boot-quarantine.tsv'")
start, end = body.index("packet = output / 'ipc_open_packet.h'"), body.index('records = [dict(row)')
changes = '''
component = root / 'playrecord-fs-device'
prep = json.loads((component / 'preparation.json').read_text())
assert sha(component / 'fs_device.cpp') == prep['sourceHashes'][str(component / 'fs_device.cpp')]
(output / 'fs_device.cpp').write_bytes((component / 'fs_device.cpp').read_bytes())
front = output / 'ipc_ack_frontend.h'
wrapper = output / 'boot-wrapper.cpp'
(output / 'playrecord_open_dispatch.h').write_bytes((experiment / 'playrecord_open_dispatch.h').read_bytes())
replace(front, '#include "es_close_after_consumption_adapter.h"', '#include "es_close_after_consumption_adapter.h"\\n#include "playrecord_open_dispatch.h"')
replace(front, '|| stmSubmitted == 41)', '|| stmSubmitted == 41 || stmSubmitted == 43)', 2)
replace(front, '|| stmSubmitted == 42)', '|| stmSubmitted == 42 || stmSubmitted == 44)', front.read_text().count('|| stmSubmitted == 42)'))
replace(front, '(stmSubmitted == 40 && !std::getenv("SHSM_POST_ES16_CLOSE_DISABLED")))',
    '(stmSubmitted == 40 && !std::getenv("SHSM_POST_ES16_CLOSE_DISABLED")) || (stmSubmitted == 42 && !std::getenv("SHSM_PLAYRECORD_OPEN_DISABLED")))')
replace(front, '            if (stmSubmitted == 40) {',
    '            if (stmSubmitted == 42) {\\n                experiment_playrecord_open_validate(context, value);\\n            }\\n            if (stmSubmitted == 40) {')
replace(front, 'experiment_post_consumption_close_ready(', 'experiment_playrecord_open_ready(', front.read_text().count('experiment_post_consumption_close_ready('))
si = output / 'si_external_delivery.h'
replace(si, '|| stmSubmitted == 42)', '|| stmSubmitted == 42 || stmSubmitted == 44)', 2)
replace(si, 'experiment_post_consumption_close_ready(', 'experiment_playrecord_open_ready(', si.read_text().count('experiment_post_consumption_close_ready('))
replace(wrapper, '    if (stmSubmitted == 41) {',
    '    if (stmSubmitted == 43) {\\n        hw::ipc_ppc_ctrl = 0x31;\\n        EventScheduler::get().schedule_after(64, [](CPUContext&, uint64_t) {\\n            hw::ipc_ppc_ctrl = (hw::ipc_ppc_ctrl & ~1u) | 2;\\n        });\\n        hw::experiment_fixture_reply_after(request, 65, [request](CPUContext& active, uint64_t) {\\n            experiment_playrecord_open_dispatch(active, request);\\n            ++stmProduced;\\n        });\\n        return;\\n    }\\n    if (stmSubmitted == 41) {')
packet = output / 'ipc_open_packet.h'
replace(packet, 'physical < 0x135e1035', 'physical < 0x135e104b')
replace(packet, '(mode != 0 && mode != 1)', '(mode != 0 && mode != 1 && mode != 3)')
replace(packet, 'path != "/title/00000001/00000002/data/setting.txt"',
    'path != "/title/00000001/00000002/data/setting.txt" && path != "/title/00000001/00000002/data/play_rec.dat"', 2)
replace(packet, '    const auto result = IOSKernel::get().open(context, path, mode);',
    '    if ((path == "/title/00000001/00000002/data/play_rec.dat") != (mode == 3)) { throw std::runtime_error("Play-record OPEN mode/path mismatch"); }\\n    const auto result = IOSKernel::get().open(context, path, mode);')
fs_source = runtime / 'src/hle/devices/fs_device.cpp'
'''
body = body[:start] + changes + body[end:]
body = body.replace("('output_62.cpp', 'output_67.cpp')", "('output_62.cpp', 'output_64.cpp', 'output_67.cpp', 'output_68.cpp')")
body = body.replace("    source.write_bytes(Path(row['source']).read_bytes())", "    source.write_bytes(Path(row['source']).read_bytes())\n    if name == 'output_67.cpp':\n        replace(source, 'loc_80240680: ;', 'loc_80240680: ;\\n    nwii::runtime::experiment_playrecord_callback_observe(ctx, 1);')\n    if name == 'output_68.cpp':\n        replace(source, 'loc_80244E30: ;', 'loc_80244E30: ;\\n    nwii::runtime::experiment_playrecord_callback_observe(ctx, 2);')\n    if name == 'output_64.cpp':\n        label = 'loc_8021CDE0: ;'\n        replace(source, label, label + '\\n    nwii::runtime::experiment_playrecord_callback_observe(ctx, 3);', source.read_text().count(label))")
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp', output / 'di_device.cpp'")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_PLAYRECORD_OPEN_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env.update(SHSM_PLAYRECORD_LAB_FILE='work/private-game/static-recomp/playrecord-fs-device/pc-owned-playrecord.bin', SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin', SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin', SHSM_ES_LAB_CONSUMPTION='1', SHSM_DI_LAB_INQUIRY_PATH='work/private-game/static-recomp/di-inquiry-device/dolphin-lab-inquiry.bin', SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF', SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')\n    result = subprocess.run([str(exe),")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-playrecord-open-boot')
path = output / 'build.json'
report = json.loads(path.read_text())
report['playrecordDevicePreparationSha256'] = hashlib.sha256(Path('work/private-game/static-recomp/playrecord-fs-device/preparation.json').read_bytes()).hexdigest()
report['limits'] = ['Real shared FS/kernel mode3 OPEN/FD4; original SDK callbacks not substituted.',
    'ACK64/reply65 are PC timing adaptations; callback completion/read/free/first screen require separate audit.']
path.write_text(json.dumps(report,indent=2) + '\n')

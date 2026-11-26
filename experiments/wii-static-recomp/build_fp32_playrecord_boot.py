"""Continue the pending real OPEN with verified single-transfer lowering."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-playrecord-open-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-fp32-playrecord-boot'").replace(
    "('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_playrecord_open_boot.py', 'verify_fp32.py')").replace(
    "'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'di_device.cpp', 'boot-quarantine.tsv'")
start, end = body.index("packet = output / 'ipc_open_packet.h'"), body.index('records = [dict(row)')
body = body[:start] + '''
from fp32_lowering import lower
front = output / 'ipc_ack_frontend.h'
wrapper = output / 'boot-wrapper.cpp'
(output / 'fp32_transfer.h').write_bytes((experiment / 'fp32_transfer.h').read_bytes())
replace(front, '#include "playrecord_open_dispatch.h"', '#include "playrecord_open_dispatch.h"\\n#include "fp32_transfer.h"')
fs_source = runtime / 'src/hle/devices/fs_device.cpp'
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
all_changes = {}
''' + body[end:]
body = body.replace("for name in ('output_62.cpp', 'output_67.cpp'):", "for name in [row['file'] for row in records]:")
body = body.replace("    source.write_bytes(Path(row['source']).read_bytes())", "    modified, changes = lower(Path(row['source']).read_text(), dol)\n    if not changes:\n        continue\n    all_changes[name] = changes\n    source.write_text(modified)")
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp', output / 'di_device.cpp'")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_PLAYRECORD_OPEN_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env.update(SHSM_PLAYRECORD_LAB_FILE='work/private-game/static-recomp/playrecord-fs-device/pc-owned-playrecord.bin', SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin', SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin', SHSM_ES_LAB_CONSUMPTION='1', SHSM_DI_LAB_INQUIRY_PATH='work/private-game/static-recomp/di-inquiry-device/dolphin-lab-inquiry.bin', SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF', SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')\n    result = subprocess.run([str(exe),")
marker = "for mode in ('live', 'disabled'):"
assert body.count(marker) == 1
body = body.replace(marker, "(output / 'lowering.json').write_text(json.dumps({'changes':all_changes,'lowererSha256':sha(experiment / 'fp32_lowering.py'),'proofSha256':sha(root / 'dolphin-fp32/comparison.json')},indent=2) + '\\n')\n" + marker)
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
path = Path('work/private-game/static-recomp/mass-fp32-playrecord-boot/build.json')
report = json.loads(path.read_text())
report['limits'] = ['Four measured FP32 transfers use exact bit conversion and existing BAT/cache; other NI guards unchanged.',
    'Only exact-single stores admitted; not all FPU or binary64 store truncation.',
    'Original pending OPEN service/callback lifecycle and fresh endpoints require the continuation audit.']
path.write_text(json.dumps(report,indent=2) + '\n')

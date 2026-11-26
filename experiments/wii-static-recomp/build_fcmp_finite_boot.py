"""Integrate the verified non-NaN compare through the existing PPC module."""
from pathlib import Path
import re
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-bias-constructors-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-fcmp-finite-boot'").replace(
    "('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_bias_constructors_boot.py', 'verify_fcmp_jit_finite.py')").replace(
    "'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'di_device.cpp', 'boot-quarantine.tsv'")
start,end = body.index("packet = output / 'ipc_open_packet.h'"),body.index('records = [dict(row)')
body = body[:start] + '''
front = output / 'ipc_ack_frontend.h'
wrapper = output / 'boot-wrapper.cpp'
for name in ('fcmp_finite_adapter.h','fcmp_ordered_adapter.h'):
    (output / name).write_bytes((experiment / name).read_bytes())
fs_source = runtime / 'src/hle/devices/fs_device.cpp'
''' + body[end:]
body = body.replace("('output_62.cpp', 'output_67.cpp')", "('output_60.cpp',)")
marker = "    source.write_bytes(Path(row['source']).read_bytes())"
assert body.count(marker) == 1
body = body.replace(marker,marker + '''
    text = source.read_text()
    pattern = re.compile(r'(    // 0x801F5028: FC010040\\n)(.*?)(?=    \\+\\+ctx\\.inst_count;\\nloc_)',re.S)
    matched = pattern.search(text)
    assert matched and 'experiment_ni_guard' in matched[2] and 'ctx.cr[0].so = un;' in matched[2]
    after = '    if (std::getenv("SHSM_FCMP_FINITE_DISABLED")) { nwii::runtime::experiment_ni_guard(ctx, 0xfc010040, 0x801f5028); }\\n    nwii::runtime::experiment_fcmp_finite(ctx, 0xfc010040);\\n'
    text = pattern.sub(lambda match: match[1] + after,text)
    source.write_text('#include "fcmp_finite_adapter.h"\\n' + text)
''')
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp', output / 'di_device.cpp'")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_FCMP_FINITE_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env.update(SHSM_PLAYRECORD_LAB_FILE='work/private-game/static-recomp/playrecord-fs-device/pc-owned-playrecord.bin',SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin',SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin',SHSM_ES_LAB_CONSUMPTION='1',SHSM_DI_LAB_INQUIRY_PATH='work/private-game/static-recomp/di-inquiry-device/dolphin-lab-inquiry.bin',SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF',SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')\n    result = subprocess.run([str(exe),")
exec(compile(body,str(parent),'exec'),{**globals(),'__file__':__file__})

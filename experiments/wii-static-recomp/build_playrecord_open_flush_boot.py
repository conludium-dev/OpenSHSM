"""Admit only observed play-record OPEN path flush; no filesystem service or writes."""
from pathlib import Path
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-es-close-after-consumption-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-playrecord-open-flush-boot'").replace(
    "('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_es_close_after_consumption_boot.py', 'verify_post_es16_close_open.py')").replace(
    "'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'di_device.cpp', 'boot-quarantine.tsv'")
start, end = body.index("packet = output / 'ipc_open_packet.h'"), body.index('records = [dict(row)')
changes = '''
front = output / 'ipc_ack_frontend.h'
wrapper = output / 'boot-wrapper.cpp'
(output / 'playrecord_open_flush.h').write_bytes((experiment / 'playrecord_open_flush.h').read_bytes())
flush = output / 'flush_syscall.h'
replace(flush, '#include "es_consumption_flush.h"', '#include "es_consumption_flush.h"\\n#include "playrecord_open_flush.h"')
replace(flush, '!experiment_es_consumption_flush(context))', '!experiment_es_consumption_flush(context) && !experiment_playrecord_open_flush(context))')
entry = output / 'mass_boot.cpp'
observer = """        if (nwii::runtime::stmSubmitted == 42) {
            for (bool cached : {false,true}) {
                std::cout << (cached ? "PLAYRECORD_PRE_SEND_CACHED" : "PLAYRECORD_PRE_SEND_PHYSICAL");
                for (unsigned index = 0; index < 64; ++index) { std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context, (cached ? 0x935e0080u : 0xd35e0080u) + index)); }
                std::cout << std::endl;
            }
        }
"""
replace(entry, '        std::cout << "BOOT_ES_LAYOUT "', observer + '        std::cout << "BOOT_ES_LAYOUT "')
fs_source = runtime / 'src/hle/devices/fs_device.cpp'
'''
body = body[:start] + changes + body[end:]
body = body.replace("('output_62.cpp', 'output_67.cpp')", "('output_62.cpp', 'output_63.cpp', 'output_67.cpp')")
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp', output / 'di_device.cpp'")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_PLAYRECORD_FLUSH_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env.update(SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin', SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin', SHSM_ES_LAB_CONSUMPTION='1', SHSM_DI_LAB_INQUIRY_PATH='work/private-game/static-recomp/di-inquiry-device/dolphin-lab-inquiry.bin', SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF', SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')\n    result = subprocess.run([str(exe),")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-playrecord-open-flush-boot')
report = json.loads((output / 'build.json').read_text())
report['limits'] = ['Only exact observed OPEN path flush; original SDK normalizes path/mode and commits packet.',
    'Filesystem service/sender/OPEN/read/write/callback not admitted; original and LAB files unchanged.']
(output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')

"""Admit only the three original ES16 flush sites before request submission."""
from pathlib import Path
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-di-inquiry-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-es-consumption-flush-boot'").replace(
    "('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_di_inquiry_boot.py', 'verify_es_consumption_dolphin.py', 'verify_es_consumption_device.py')").replace(
    "'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'di_device.cpp', 'boot-quarantine.tsv'")
start, end = body.index("packet = output / 'ipc_open_packet.h'"), body.index('records = [dict(row)')
changes = '''
front = output / 'ipc_ack_frontend.h'
flush = output / 'flush_syscall.h'
(output / 'es_consumption_flush.h').write_bytes((experiment / 'es_consumption_flush.h').read_bytes())
(output / 'es_consumption_adapter.h').write_bytes((experiment / 'es_consumption_adapter.h').read_bytes())
(output / 'es_device.cpp').write_bytes(Path('work/private-game/static-recomp/es-consumption-device/es_device.cpp').read_bytes())
replace(flush, '#include "es_di_ticket_flush.h"', '#include "es_di_ticket_flush.h"\\n#include "es_consumption_flush.h"')
replace(flush, '!experiment_es_di_ticket_flush(context))', '!experiment_es_di_ticket_flush(context) && !experiment_es_consumption_flush(context))')
wrapper = output / 'boot-wrapper.cpp'
entry = output / 'mass_boot.cpp'
observer = """        if (nwii::runtime::stmSubmitted == 38) {
            for (bool cached : {false, true}) {
                std::cout << (cached ? "ES16_PACKET_CACHED" : "ES16_PACKET_PHYSICAL");
                for (unsigned index = 0; index < 64; ++index) { std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context, (cached ? 0x935e0080u : 0xd35e0080u) + index)); }
                std::cout << std::endl;
                std::cout << (cached ? "ES16_VECTOR_CACHED" : "ES16_VECTOR_PHYSICAL");
                for (unsigned index = 0; index < 24; ++index) { std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context, (cached ? 0x8053fd70u : 0xc053fd70u) + index)); }
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
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_ES_CONSUMPTION_FLUSH_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env.update(SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin', SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin', SHSM_ES_LAB_CONSUMPTION='1', SHSM_DI_LAB_INQUIRY_PATH='work/private-game/static-recomp/di-inquiry-device/dolphin-lab-inquiry.bin', SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF', SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')\n    result = subprocess.run([str(exe),")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-es-consumption-flush-boot')
report = json.loads((output / 'build.json').read_text())
report['limits'] = ['Existing ES16 device linked with explicit measured LAB policy; three original flush sites scoped to retired inquiry topology.',
    'All125 PPC sources unchanged/three objects rebuilt122 retained; ES16 submission/return still require verification.']
(output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')

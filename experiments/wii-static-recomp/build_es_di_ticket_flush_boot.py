"""Admit only measured ticket-view output/vector flush in existing native pipeline."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-di-burst-cache-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-es-di-ticket-flush-boot'").replace(
    "('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_di_burst_cache_boot.py', 'verify_di_burst_es_vector.py', 'verify_es_di_ticket_device.py')").replace(
    "'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'di_device.cpp', 'boot-quarantine.tsv'")
start, end = body.index("packet = output / 'ipc_open_packet.h'"), body.index('records = [dict(row)')
changes = '''
front = output / 'ipc_ack_frontend.h'
flush = output / 'flush_syscall.h'
(output / 'es_di_ticket_flush.h').write_bytes((experiment / 'es_di_ticket_flush.h').read_bytes())
(output / 'es_di_ticket_adapter.h').write_bytes((experiment / 'es_di_ticket_adapter.h').read_bytes())
(output / 'es_device.cpp').write_bytes(Path('work/private-game/static-recomp/es-di-ticket-device/es_device.cpp').read_bytes())
replace(flush, '#include "stm_async_dispatch.h"', '#include "stm_async_dispatch.h"\\n#include "es_di_ticket_flush.h"')
replace(flush, '&& !sysconfPathFlush)', '&& !sysconfPathFlush && !experiment_es_di_ticket_flush(context))')
wrapper = output / 'boot-wrapper.cpp'
fs_source = runtime / 'src/hle/devices/fs_device.cpp'
'''
body = body[:start] + changes + body[end:]
body = body.replace("('output_62.cpp', 'output_67.cpp')", "('output_62.cpp', 'output_63.cpp', 'output_67.cpp')")
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp', output / 'di_device.cpp'")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_ES_DI_TICKET_FLUSH_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'\n    env['SHSM_ES_TICKET_PATH'] = 'work/private-game/disc/DATA/ticket.bin'\n    env['SHSM_SC_LAB_FILE'] = '_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF'\n    env['SHSM_SC_LAB_PRODUCT'] = '_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt'\n    result = subprocess.run([str(exe),")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-es-di-ticket-flush-boot')
report = json.loads((output / 'build.json').read_text())
report['limits'] = ['Existing ES class has own-Wii ticket service; only two bounded output/vector flush sites admitted.',
    'Native request submission/IOCTLV reply and original SDK return still require verification; no forced packet/vector normalization.']
(output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')

"""Integrate the original-verified subtraction into the existing125-object startup."""
from pathlib import Path
from general_subtract_lowering import lower

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-bias-alias-initializer-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-general-subtract-boot'").replace(
    "('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_bias_alias_initializer_boot.py','verify_general_subtract_native.py','verify_general_subtract_targeted.py','verify_general_subtract_contract.py')").replace(
    "'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'di_device.cpp', 'boot-quarantine.tsv'")
start, end = body.index("packet = output / 'ipc_open_packet.h'"), body.index('records = [dict(row)')
body = body[:start] + '''
front = output / 'ipc_ack_frontend.h'
wrapper = output / 'boot-wrapper.cpp'
assert sha(output / 'single_arithmetic_adapter.h') == sha(experiment / 'single_arithmetic_adapter.h')
(output / 'general_subtract_adapter.h').write_bytes((experiment / 'general_subtract_adapter.h').read_bytes())
fs_source = runtime / 'src/hle/devices/fs_device.cpp'
''' + body[end:]
body = body.replace("('output_62.cpp', 'output_67.cpp')", "('output_26.cpp',)")
marker = "    source.write_bytes(Path(row['source']).read_bytes())"
assert body.count(marker) == 1
body = body.replace(marker, marker + '''
    text, changes = lower(source.read_text(),Path('work/private-game/disc/DATA/sys/main.dol').read_bytes())
    assert len(changes) == 1
    source.write_text(text)
''')
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp', output / 'di_device.cpp'")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_GENERAL_SUBTRACT_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env.update(SHSM_PLAYRECORD_LAB_FILE='work/private-game/static-recomp/playrecord-fs-device/pc-owned-playrecord.bin',SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin',SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin',SHSM_ES_LAB_CONSUMPTION='1',SHSM_DI_LAB_INQUIRY_PATH='work/private-game/static-recomp/di-inquiry-device/dolphin-lab-inquiry.bin',SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF',SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')\n    result = subprocess.run([str(exe),")
body = body.replace("'Exactly fourth FS OPEN; private existing FS specialization avoids synthetic VNand initialization.'",
    "'Exact general-subtraction body changed;124 objects retained, no new backend or control flow.'")
exec(compile(body, str(parent), 'exec'), {**globals(), '__file__': __file__})

"""Bind the exact measured operand routing without changing the existing arithmetic core."""
from pathlib import Path
import re

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-bias-block-registers-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-multiply-register-boot'").replace(
    "('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_bias_block_registers_boot.py','verify_multiply_register.py','verify_multiply_register_targeted.py','verify_multiply_register_contract.py')").replace(
    "'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'di_device.cpp', 'boot-quarantine.tsv'")
start,end = body.index("packet = output / 'ipc_open_packet.h'"),body.index('records = [dict(row)')
body = body[:start] + '''
front = output / 'ipc_ack_frontend.h'
wrapper = output / 'boot-wrapper.cpp'
component = root / 'multiply-register-component'
prep = json.loads((component / 'preparation.json').read_text())
assert prep['parentHelperSha256'] == sha(output / 'single_arithmetic_adapter.h')
assert prep['headerSha256'] == sha(component / 'multiply_register_adapter.h')
(output / 'multiply_register_adapter.h').write_bytes((component / 'multiply_register_adapter.h').read_bytes())
fs_source = runtime / 'src/hle/devices/fs_device.cpp'
''' + body[end:]
body = body.replace("('output_62.cpp', 'output_67.cpp')", "('output_26.cpp',)")
marker = "    source.write_bytes(Path(row['source']).read_bytes())"
assert body.count(marker) == 1
body = body.replace(marker,marker + '''
    text = source.read_text()
    pattern = re.compile(r'(    // 0x800D7570: EC010032\\n)(.*?)(?=    \\+\\+ctx\\.inst_count;\\nloc_)',re.S)
    assert len(pattern.findall(text)) == 1
    matched = pattern.search(text)
    assert 'experiment_ni_guard' in matched[2] and 'fmuls' in matched[2]
    after = '    if (std::getenv("SHSM_MULTIPLY_REGISTER_DISABLED")) { nwii::runtime::experiment_ni_guard(ctx, 0xec010032, 0x800d7570); }\\n    nwii::runtime::experiment_multiply_register(ctx, 0xec010032);\\n'
    source.write_text('#include "multiply_register_adapter.h"\\n' + pattern.sub(lambda match: match[1] + after,text))
''')
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp', output / 'di_device.cpp'")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_MULTIPLY_REGISTER_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env.update(SHSM_PLAYRECORD_LAB_FILE='work/private-game/static-recomp/playrecord-fs-device/pc-owned-playrecord.bin',SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin',SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin',SHSM_ES_LAB_CONSUMPTION='1',SHSM_DI_LAB_INQUIRY_PATH='work/private-game/static-recomp/di-inquiry-device/dolphin-lab-inquiry.bin',SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF',SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')\n    result = subprocess.run([str(exe),")
exec(compile(body,str(parent),'exec'),{**globals(),'__file__':__file__})

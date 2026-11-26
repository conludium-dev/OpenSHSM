"""Integrate both verified operations and the captured second subtraction without bypassing the constructor."""
from pathlib import Path
import re

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-bias-register-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-single-arithmetic-boot'").replace(
    "('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_bias_register_boot.py','verify_single_arithmetic_native.py','verify_single_arithmetic_targeted.py','verify_single_arithmetic_contract.py','verify_fsubs_second.py')").replace(
    "'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'di_device.cpp', 'boot-quarantine.tsv'")
start,end = body.index("packet = output / 'ipc_open_packet.h'"),body.index('records = [dict(row)')
body = body[:start] + '''
front = output / 'ipc_ack_frontend.h'
wrapper = output / 'boot-wrapper.cpp'
(output / 'single_arithmetic_adapter.h').write_bytes((experiment / 'single_arithmetic_adapter.h').read_bytes())
fs_source = runtime / 'src/hle/devices/fs_device.cpp'
''' + body[end:]
body = body.replace("('output_62.cpp', 'output_67.cpp')", "('output_20.cpp',)")
marker = "    source.write_bytes(Path(row['source']).read_bytes())"
assert body.count(marker) == 1
body = body.replace(marker,marker + '''
    text = source.read_text()
    pattern = re.compile(r'(    // 0x(800A8F20|800A8F30): (EC220824|EC000072)\\n)(.*?)(?=    \\+\\+ctx\\.inst_count;\\nloc_)',re.S)
    assert len(pattern.findall(text)) == 2
    def arithmetic(match):
        assert 'experiment_ni_guard' in match[4] and ('fdivs' in match[4] or 'fmuls' in match[4])
        address,opcode = int(match[2],16),int(match[3],16)
        return match[1] + f'    if (std::getenv("SHSM_SINGLE_ARITHMETIC_DISABLED")) {{ nwii::runtime::experiment_ni_guard(ctx, 0x{opcode:08x}, 0x{address:08x}); }}\\n    nwii::runtime::experiment_single_arithmetic(ctx, 0x{opcode:08x});\\n'
    text = pattern.sub(arithmetic,text)
    before = '    nwii::runtime::experiment_ni_guard(ctx, 0xec421828, 0x800a8f2c);\\n    ctx.fpr[2] = (float)(ctx.fpr[2] - ctx.fpr[3]); // fsubs'
    assert text.count(before) == 1
    text = text.replace(before,'    nwii::runtime::experiment_fsubs_integer_bias(ctx, 0xec421828);')
    source.write_text('#include "single_arithmetic_adapter.h"\\n' + text)
''')
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp', output / 'di_device.cpp'")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_SINGLE_ARITHMETIC_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env.update(SHSM_PLAYRECORD_LAB_FILE='work/private-game/static-recomp/playrecord-fs-device/pc-owned-playrecord.bin',SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin',SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin',SHSM_ES_LAB_CONSUMPTION='1',SHSM_DI_LAB_INQUIRY_PATH='work/private-game/static-recomp/di-inquiry-device/dolphin-lab-inquiry.bin',SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF',SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')\n    result = subprocess.run([str(exe),")
exec(compile(body,str(parent),'exec'),{**globals(),'__file__':__file__})

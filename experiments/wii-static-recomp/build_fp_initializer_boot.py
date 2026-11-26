"""Integrate the verified original initializer without general fsubs claims."""
from pathlib import Path
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-fp32-playrecord-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-fp-initializer-boot'").replace(
    "('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_fp32_playrecord_boot.py', 'verify_fp_initializer_dolphin.py')").replace(
    "'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'di_device.cpp', 'boot-quarantine.tsv'")
start, end = body.index("packet = output / 'ipc_open_packet.h'"), body.index('records = [dict(row)')
body = body[:start] + '''
front = output / 'ipc_ack_frontend.h'
wrapper = output / 'boot-wrapper.cpp'
for name in ('fsubs_integer_bias.h','fp_initializer_probe.h'):
    (output / name).write_bytes((experiment / name).read_bytes())
replace(front, '#include "fp32_transfer.h"', '#include "fp32_transfer.h"\\n#include "fsubs_integer_bias.h"')
replace(wrapper, 'int main(int argc, char** argv) {',
    '#include "fp_initializer_probe.h"\\nint main(int argc, char** argv) {\\n    if (argc == 2 && std::string(argv[1]) == "--fp-initializer-probe") { return experiment_fp_initializer_probe(); }')
entry = output / 'mass_boot.cpp'
observer = """        if (context.pc == 0x80212ff4 && nwii::runtime::stmSubmitted == 44) {
            std::cout << "PLAYRECORD_READ_PREP_STATE " << std::hex << context.gpr[3] << ' ' << context.gpr[4] << ' '
                << nwii::runtime::bat_memory_read32(context,0x80528a40) << ' ' << nwii::runtime::bat_memory_read32(context,0x804931d0) << ' '
                << nwii::runtime::bat_memory_read32(context,0x804b2b4c) << std::dec << std::endl;
            for (bool cached : {false,true}) {
                std::cout << (cached ? "PLAYRECORD_READ_PREP_CACHED" : "PLAYRECORD_READ_PREP_PHYSICAL");
                for (unsigned index = 0; index < 64; ++index) { std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context,(cached ? 0x935e00e0u : 0xd35e00e0u) + index)); }
                std::cout << std::endl;
            }
        }
"""
replace(entry, '        std::cout << "BOOT_ES_LAYOUT "', observer + '        std::cout << "BOOT_ES_LAYOUT "')
fs_source = runtime / 'src/hle/devices/fs_device.cpp'
''' + body[end:]
body = body.replace("('output_62.cpp', 'output_67.cpp')", "('output_1.cpp',)")
old = '    source.write_bytes(Path(row[\'source\']).read_bytes())'
new = '''    source.write_bytes(Path(row['source']).read_bytes())
    replace(source, '    nwii::runtime::experiment_ni_guard(ctx, 0xec000828, 0x8000c31c);\\n    ctx.fpr[0] = (float)(ctx.fpr[0] - ctx.fpr[1]); // fsubs',
        '    nwii::runtime::experiment_fsubs_integer_bias(ctx, 0xec000828);')
    replace(source, 'loc_8000C328: ;', 'loc_8000C328: ;\\n    if (ctx.msr == 0xa032 && nwii::runtime::stmSubmitted == 44) { std::cout << "FP_INITIALIZER_SOURCE " << std::hex << ctx.fpscr << " " << nwii::runtime::bat_memory_read32(ctx,0x80529158) << " " << nwii::runtime::bat_memory_read32(ctx,0x8052915c) << std::dec << std::endl; }')
'''
assert body.count(old) == 1
body = body.replace(old,new)
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp', output / 'di_device.cpp'")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_FP_INITIALIZER_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env.update(SHSM_PLAYRECORD_LAB_FILE='work/private-game/static-recomp/playrecord-fs-device/pc-owned-playrecord.bin',SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin',SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin',SHSM_ES_LAB_CONSUMPTION='1',SHSM_DI_LAB_INQUIRY_PATH='work/private-game/static-recomp/di-inquiry-device/dolphin-lab-inquiry.bin',SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF',SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')\n    result = subprocess.run([str(exe),")
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
path = Path('work/private-game/static-recomp/mass-fp-initializer-boot/build.json')
report = json.loads(path.read_text())
report['limits'] = ['One original fsubs site uses verified signed-int bias arithmetic; other fsubs remain guarded.',
    'Whole generated14-instruction initializer probe on this same125-object module; real continuation requires fresh audit.',
    'No forced original result/global/FP status; no physical Wii or full FPU claim.']
path.write_text(json.dumps(report,indent=2) + '\n')

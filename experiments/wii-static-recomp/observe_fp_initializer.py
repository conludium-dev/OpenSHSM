"""Read actual operands at the existing fsubs guard, retaining all125 PPC objects."""
from pathlib import Path
import ast

parent = Path('experiments/wii-static-recomp/observe_es_vector_boot.py')
body = parent.read_text().replace('mass-es-open-boot','mass-fp32-playrecord-boot').replace(
    'mass-es-vector-observer','mass-fp-initializer-observer').replace(
    'audit_es_open_boot.py','audit_fp32_playrecord_boot.py').replace(
    "'es_device.cpp', 'boot-quarantine.tsv'", "'es_device.cpp', 'di_device.cpp', 'boot-quarantine.tsv'").replace(
    "output / 'es_device.cpp']", "output / 'es_device.cpp', output / 'di_device.cpp']")
node = next(node for node in ast.parse(body).body if isinstance(node,ast.Assign)
    and any(isinstance(target,ast.Name) and target.id == 'observer' for target in node.targets))
observer = r'''        if (context.pc == 0x8000c2f4 && context.lr == 0x8021e8f4 && context.msr == 0xa032) {
            std::cout << "FP_INITIALIZER_OPERANDS " << std::hex
                << std::bit_cast<uint64_t>(context.fpr[0]) << ' ' << std::bit_cast<uint64_t>(context.fpr[1]) << ' '
                << std::bit_cast<uint64_t>(context.ps1[0]) << ' ' << std::bit_cast<uint64_t>(context.ps1[1]) << ' '
                << context.fpscr << ' ' << context.gpr[1] << ' '
                << nwii::runtime::bat_memory_read32(context,0x8052861c) << ' '
                << nwii::runtime::bat_memory_read32(context,0x8052915c) << ' '
                << nwii::runtime::bat_memory_read32(context,0x80529158) << std::dec << std::endl;
        }
'''
body = body.replace(ast.get_source_segment(body,node.value),repr(observer)).replace(
    "assert 'ES_VECTOR_CACHED 8053ff20 8' in result.stdout", "assert 'FP_INITIALIZER_OPERANDS ' in result.stdout").replace(
    'pc=80212ff4 lr=80242fc8 msr=a032','pc=8000c2f4 lr=8021e8f4 msr=a032').replace(
    "('ES_', 'BOOT_BOUNDARY'", "('FP_INITIALIZER_', 'BOOT_BOUNDARY'")
body = body.replace("env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}",
    "env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}\n"
    "env.update(SHSM_PLAYRECORD_LAB_FILE='work/private-game/static-recomp/playrecord-fs-device/pc-owned-playrecord.bin',SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin',SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin',SHSM_ES_LAB_CONSUMPTION='1',SHSM_DI_LAB_INQUIRY_PATH='work/private-game/static-recomp/di-inquiry-device/dolphin-lab-inquiry.bin',SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF',SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')")
exec(compile(body,str(parent),'exec'),{'__file__':__file__})

"""Read actual asynchronous OPEN after ES16/CLOSE, retaining all original PPC objects."""
from pathlib import Path
import ast

parent = Path('experiments/wii-static-recomp/observe_es_vector_boot.py')
body = parent.read_text().replace('mass-es-open-boot', 'mass-es-close-after-consumption-boot').replace(
    'mass-es-vector-observer', 'mass-post-es16-close-open-observer').replace(
    'audit_es_open_boot.py', 'audit_es_close_after_consumption_boot.py').replace(
    "'es_device.cpp', 'boot-quarantine.tsv'", "'es_device.cpp', 'di_device.cpp', 'boot-quarantine.tsv'").replace(
    "output / 'es_device.cpp']", "output / 'es_device.cpp', output / 'di_device.cpp']")
node = next(node for node in ast.parse(body).body if isinstance(node, ast.Assign) and
    any(isinstance(target, ast.Name) and target.id == 'observer' for target in node.targets))
observer = r'''        if (context.pc == 0x80212ff4 && context.lr == 0x8024250c && context.msr == 0xa032 && nwii::runtime::stmSubmitted == 42) {
            std::cout << "POST_CLOSE_OPEN_ARGS" << std::hex;
            for (unsigned index : {1u,3u,4u,26u,27u,28u,29u,30u,31u}) { std::cout << ' ' << context.gpr[index]; }
            std::cout << std::dec << std::endl;
            for (bool cached : {false,true}) {
                for (const auto& region : std::array<std::tuple<const char*,uint32_t,unsigned>,2>{
                    std::tuple{"WORK",0x135e1020,320u}, std::tuple{"PACKET",0x135e0080,64u}}) {
                    std::cout << "POST_CLOSE_OPEN_" << std::get<0>(region) << (cached ? "_CACHED" : "_PHYSICAL");
                    for (unsigned index = 0; index < std::get<2>(region); ++index) {
                        std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context,
                            (std::get<1>(region) | (cached ? 0x80000000u : 0xc0000000u)) + index));
                    }
                    std::cout << std::endl;
                }
            }
            std::cout << "POST_CLOSE_OPEN_LAYOUT" << std::hex;
            for (uint32_t address : {0x80528ce8u,0x804b2b4cu,0x8052ac50u,0x804983c8u,0x804b2a80u,0x804b2a84u,0x804b2a88u,0x804b2a8cu}) {
                std::cout << ' ' << nwii::runtime::bat_memory_read32(context,address);
            }
            std::cout << std::dec << std::endl;
        }
'''
body = body.replace(ast.get_source_segment(body, node.value), repr(observer)).replace(
    "assert 'ES_VECTOR_CACHED 8053ff20 8' in result.stdout", "assert 'POST_CLOSE_OPEN_ARGS ' in result.stdout").replace(
    'pc=80212ff4 lr=80242fc8 msr=a032', 'pc=80212ff4 lr=8024250c msr=a032').replace(
    "('ES_', 'BOOT_BOUNDARY'", "('POST_CLOSE_OPEN_', 'BOOT_BOUNDARY'")
body = body.replace("env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}",
    "env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}\n"
    "env.update(SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin', SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin', SHSM_ES_LAB_CONSUMPTION='1', SHSM_DI_LAB_INQUIRY_PATH='work/private-game/static-recomp/di-inquiry-device/dolphin-lab-inquiry.bin', SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF', SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})

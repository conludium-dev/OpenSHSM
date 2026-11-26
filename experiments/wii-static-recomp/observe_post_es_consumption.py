"""Read the next actual sender packet without changing any original PPC object."""
from pathlib import Path
import ast

parent = Path('experiments/wii-static-recomp/observe_es_vector_boot.py')
body = parent.read_text().replace('mass-es-open-boot', 'mass-es-consumption-boot').replace(
    'mass-es-vector-observer', 'mass-post-es-consumption-observer').replace(
    'audit_es_open_boot.py', 'audit_es_consumption_boot.py').replace(
    "'es_device.cpp', 'boot-quarantine.tsv'", "'es_device.cpp', 'di_device.cpp', 'boot-quarantine.tsv'").replace(
    "output / 'es_device.cpp']", "output / 'es_device.cpp', output / 'di_device.cpp']")
node = next(node for node in ast.parse(body).body if isinstance(node, ast.Assign) and
    any(isinstance(target, ast.Name) and target.id == 'observer' for target in node.targets))
observer = r'''        if (context.pc == 0x80241c30 && context.lr == 0x80242384 && context.msr == 0x2032 && nwii::runtime::stmSubmitted == 40) {
            std::cout << "ES_NEXT_ARGUMENTS" << std::hex;
            for (unsigned index : {1u,3u,4u,5u,6u,29u,30u,31u}) { std::cout << ' ' << context.gpr[index]; }
            std::cout << std::dec << std::endl;
            const uint32_t physical = context.gpr[4];
            if (physical != 0x135e0080 && physical != 0x135e00e0) { throw std::runtime_error("Next sender diagnostic owner outside bounded pool"); }
            const uint32_t cached = physical | 0x80000000u;
            for (bool cache : {false,true}) {
                std::cout << (cache ? "ES_NEXT_PACKET_CACHED" : "ES_NEXT_PACKET_PHYSICAL");
                for (unsigned index = 0; index < 64; ++index) {
                    std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context, (cache ? cached : physical | 0xc0000000u) + index));
                }
                std::cout << std::endl;
            }
            const uint32_t command = nwii::runtime::bat_memory_read32(context, cached);
            if (command == 6) {
                for (unsigned index : {0u,1u}) {
                    const uint32_t pointer = nwii::runtime::bat_memory_read32(context, cached + 16 + index * 8);
                    const uint32_t size = nwii::runtime::bat_memory_read32(context, cached + 20 + index * 8);
                    std::cout << "ES_NEXT_BUFFER " << index << ' ' << std::hex << pointer << ' ' << size << std::dec << std::endl;
                    if (!pointer && !size) { continue; }
                    if (!size || size > 1024 || pointer < 0x400000 || pointer > 0x18000000 - size) {
                        throw std::runtime_error("Next sender diagnostic backing outside bounded capture");
                    }
                    for (bool cache : {false,true}) {
                        std::cout << (cache ? "ES_NEXT_DATA_CACHED" : "ES_NEXT_DATA_PHYSICAL") << ' ' << index;
                        for (unsigned offset = 0; offset < size; ++offset) {
                            std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context, (pointer | (cache ? 0x80000000u : 0xc0000000u)) + offset));
                        }
                        std::cout << std::endl;
                    }
                }
            }
        }
'''
body = body.replace(ast.get_source_segment(body, node.value), repr(observer)).replace(
    "assert 'ES_VECTOR_CACHED 8053ff20 8' in result.stdout", "assert 'ES_NEXT_ARGUMENTS ' in result.stdout").replace(
    "assert 'BOOT_BOUNDARY pc=80212ff4 lr=80242fc8 msr=a032' in result.stdout",
    "assert 'BOOT_BOUNDARY pc=80241c30 lr=80242384 msr=2032' in result.stdout")
body = body.replace("env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}",
    "env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}\n"
    "env.update(SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin', SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin', SHSM_ES_LAB_CONSUMPTION='1', SHSM_DI_LAB_INQUIRY_PATH='work/private-game/static-recomp/di-inquiry-device/dolphin-lab-inquiry.bin', SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF', SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})

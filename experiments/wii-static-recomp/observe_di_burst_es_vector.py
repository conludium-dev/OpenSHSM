"""Read actual post-burst ES vector/request, preserving all125 native PPC objects."""
from pathlib import Path
import ast

parent = Path('experiments/wii-static-recomp/observe_es_vector_boot.py')
body = parent.read_text().replace('mass-es-open-boot', 'mass-di-burst-cache-boot').replace(
    'mass-es-vector-observer', 'mass-di-burst-es-vector-observer').replace(
    'audit_es_open_boot.py', 'audit_di_burst_cache_boot.py')
body = body.replace("'es_device.cpp', 'boot-quarantine.tsv'", "'es_device.cpp', 'di_device.cpp', 'boot-quarantine.tsv'").replace(
    "output / 'es_device.cpp']", "output / 'es_device.cpp', output / 'di_device.cpp']")
node = next(node for node in ast.parse(body).body if isinstance(node, ast.Assign) and
    any(isinstance(target, ast.Name) and target.id == 'observer' for target in node.targets))
observer = r'''        if (context.pc == 0x80212ff4 && context.lr == 0x80242fc8 && context.msr == 0xa032 && nwii::runtime::stmSubmitted == 36) {
            std::cout << "ES_BURST_ARGUMENTS" << std::hex;
            for (unsigned index : {1u, 3u, 4u, 7u, 27u, 28u, 29u, 30u, 31u}) { std::cout << ' ' << context.gpr[index]; }
            std::cout << '\n';
            std::cout << "ES_BURST_LAYOUT";
            for (uint32_t address : {0x80528ce8u, 0x804b2b4cu, 0x804b2a80u, 0x804b2a84u, 0x804b2a88u, 0x804b2a8cu, 0x80492934u, 0x8052ac44u, 0x8052ac50u}) {
                std::cout << ' ' << nwii::runtime::bat_memory_read32(context, address);
            }
            const auto ipc = nwii::runtime::hw::experiment_ipc_snapshot();
            std::cout << ' ' << ipc.ppcControl << ' ' << ipc.ppcMessage << ' ' << ipc.armMessage << std::dec << '\n';
            for (const auto& region : std::array<std::tuple<const char*, uint32_t, unsigned>, 5>{
                std::tuple{"ES_BURST_PACKET_CACHED", context.gpr[29], 64u},
                std::tuple{"ES_BURST_PACKET_PHYSICAL", context.gpr[29] | 0x40000000u, 64u},
                std::tuple{"ES_BURST_VECTOR_CACHED", context.gpr[30], 64u},
                std::tuple{"ES_BURST_VECTOR_PHYSICAL", context.gpr[30] | 0x40000000u, 64u},
                std::tuple{"ES_BURST_INQUIRY_PACKET", 0x935e00e0u, 64u}}) {
                std::cout << std::get<0>(region);
                for (unsigned index = 0; index < std::get<2>(region); ++index) {
                    std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context, std::get<1>(region) + index));
                }
                std::cout << '\n';
            }
            const uint32_t count = nwii::runtime::bat_memory_read32(context, context.gpr[29] + 16) + nwii::runtime::bat_memory_read32(context, context.gpr[29] + 20);
            if (count > 4) { throw std::runtime_error("Observer vector count outside bounded profile"); }
            for (unsigned index = 0; index < count; ++index) {
                const uint32_t address = nwii::runtime::bat_memory_read32(context, context.gpr[30] + index * 8);
                const uint32_t length = nwii::runtime::bat_memory_read32(context, context.gpr[30] + index * 8 + 4);
                std::cout << "ES_BURST_VECTOR_INFO " << index << ' ' << std::hex << address << ' ' << length << std::dec << '\n';
                if (!length && !address) { continue; }
                if (!length || length > 1024 || address < 0x80400000 || address > 0x80550000 - length) { throw std::runtime_error("Observer vector backing outside bounded profile"); }
                for (bool cached : {false, true}) {
                    std::cout << (cached ? "ES_BURST_DATA_CACHED" : "ES_BURST_DATA_PHYSICAL") << ' ' << index;
                    for (unsigned byte = 0; byte < length; ++byte) {
                        std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context, (cached ? address : address | 0x40000000u) + byte));
                    }
                    std::cout << '\n';
                }
            }
        }
'''
body = body.replace(ast.get_source_segment(body, node.value), repr(observer)).replace(
    "assert 'ES_VECTOR_CACHED 8053ff20 8' in result.stdout", "assert 'ES_BURST_ARGUMENTS ' in result.stdout")
body = body.replace("env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}",
    "env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}\nenv['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'\nenv['SHSM_SC_LAB_FILE'] = '_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF'\nenv['SHSM_SC_LAB_PRODUCT'] = '_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt'")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})

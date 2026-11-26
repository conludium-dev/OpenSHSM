"""Read prepared original SYSCONF callback/control state, without changing PPC objects."""
from pathlib import Path
import ast
import hashlib
import json

parent = Path('experiments/wii-static-recomp/observe_es_vector_boot.py')
body = parent.read_text().replace('mass-es-open-boot', 'mass-es-close-boot').replace(
    'mass-es-vector-observer', 'mass-sysconf-payload-observer').replace('audit_es_open_boot.py', 'audit_es_close_boot.py')
node = next(node for node in ast.parse(body).body if isinstance(node, ast.Assign) and
    any(isinstance(target, ast.Name) and target.id == 'observer' for target in node.targets))
observer = r'''        if (context.pc == 0x80212ff4 && context.lr == 0x8024250c && context.msr == 0xa032) {
            std::cout << "SC_FLUSH_ARGUMENTS" << std::hex;
            for (unsigned index : {1u, 3u, 4u, 27u, 29u, 31u}) { std::cout << ' ' << context.gpr[index]; }
            std::cout << std::dec << '\n';
            for (bool cached : {false, true}) {
                for (auto [label, physical, length] : {std::tuple<const char*, uint32_t, unsigned>{"WORK", 0x135e1020, 0x140},
                    {"CONTROL", 0x4b3000, 0x190}, {"PACKET", 0x135e0080, 64},
                    {"CONF_HEAD", 0x4b31a0, 32}, {"CONF_TAIL", 0x4b7198, 8}}) {
                    std::cout << "SC_" << label << (cached ? "_CACHED" : "_PHYSICAL");
                    for (unsigned index = 0; index < length; ++index) {
                        std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context, physical + index +
                            (cached ? 0x80000000 : 0xc0000000)));
                    }
                    std::cout << '\n';
                }
            }
            std::cout << "SC_FLAGS";
            for (uint32_t address : {0x8052b008u, 0x8052b01cu, 0x8052b01eu}) {
                std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context, address));
            }
            std::cout << '\n';
            const auto bootInfo = nwii::runtime::bat_memory_read32(context, 0x8052aa70);
            std::cout << "SC_BOOT_PROFILE" << std::hex << ' ' << bootInfo << ' '
                << (bootInfo ? nwii::runtime::bat_memory_read32(context, bootInfo + 0x2c) : 0)
                << std::dec << std::endl;
        }
'''
literal = ast.get_source_segment(body, node.value)
assert body.count(literal) == 1
body = body.replace(literal, repr(observer))
body = body.replace("env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}",
    "env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}\nenv['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'")
body = body.replace("assert 'ES_VECTOR_CACHED 8053ff20 8' in result.stdout", "assert 'SC_FLAGS 1 1 1' in result.stdout")
body = body.replace('pc=80212ff4 lr=80242fc8 msr=a032', 'pc=80212ff4 lr=8024250c msr=a032').replace(
    "('ES_', 'BOOT_BOUNDARY'", "('SC_', 'BOOT_BOUNDARY'")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-sysconf-payload-observer/observation.json')
report = json.loads(path.read_text())
report['parentObserverSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Read-only native diagnosis before first SYSCONF OPEN submission. All125 objects/headers/backend/permissions retained.',
    'Original SDK prepares callback/control/empty SC buffer; not file contents, completed callback/read, physical Wii or complete retail behavior.']
path.write_text(json.dumps(report, indent=2) + '\n')

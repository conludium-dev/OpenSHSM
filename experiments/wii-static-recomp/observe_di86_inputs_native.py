"""Observe the actual first DI86 command/callback state, retaining all125 native PPC objects."""
from pathlib import Path
import ast
import hashlib
import json

parent = Path('experiments/wii-static-recomp/observe_es_vector_boot.py')
body = parent.read_text().replace('mass-es-open-boot', 'mass-di-open-boot').replace(
    'mass-es-vector-observer', 'mass-di86-inputs-observer').replace('audit_es_open_boot.py', 'audit_di_open_boot.py')
body = body.replace("'es_device.cpp', 'boot-quarantine.tsv'", "'es_device.cpp', 'di_device.cpp', 'boot-quarantine.tsv'")
body = body.replace("output / 'es_device.cpp']", "output / 'es_device.cpp', output / 'di_device.cpp']")
node = next(node for node in ast.parse(body).body if isinstance(node, ast.Assign) and
    any(isinstance(target, ast.Name) and target.id == 'observer' for target in node.targets))
observer = r'''        if (context.pc == 0x80241c30 && context.lr == 0x80242384 && nwii::runtime::stmSubmitted == 30) {
            std::cout << "DI86_INPUTS" << std::hex;
            for (uint32_t address : {0x80528a98u, 0x8052ac7cu, 0x8052ac80u, 0x8052ac94u, 0x8052afc4u}) {
                std::cout << ' ' << nwii::runtime::bat_memory_read32(context, address);
            }
            std::cout << std::dec << '\n';
            for (const auto& region : std::array<std::tuple<const char*, uint32_t, unsigned>, 6>{
                std::tuple{"DI86_PACKET_CACHED", 0x935e0080u, 64u},
                std::tuple{"DI86_PACKET_PHYSICAL", 0xd35e0080u, 64u},
                std::tuple{"DI86_COMMAND_CACHED", 0x935e2560u, 32u},
                std::tuple{"DI86_COMMAND_PHYSICAL", 0xd35e2560u, 32u},
                std::tuple{"DI86_CALLBACK_STATE", 0x804983a0u, 32u},
                std::tuple{"DI86_CONTROL", 0x8052ac78u, 40u}}) {
                std::cout << std::get<0>(region);
                for (unsigned index = 0; index < std::get<2>(region); ++index) {
                    std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context, std::get<1>(region) + index));
                }
                std::cout << '\n';
            }
        }
'''
body = body.replace(ast.get_source_segment(body, node.value), repr(observer))
body = body.replace("env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}",
    "env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}\nenv['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'\nenv['SHSM_SC_LAB_FILE'] = '_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF'\nenv['SHSM_SC_LAB_PRODUCT'] = '_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt'")
body = body.replace("assert 'ES_VECTOR_CACHED 8053ff20 8' in result.stdout", "assert 'DI86_INPUTS ' in result.stdout")
body = body.replace('pc=80212ff4 lr=80242fc8 msr=a032', 'pc=80241c30 lr=80242384 msr=2032').replace(
    "('ES_', 'BOOT_BOUNDARY'", "('DI86_', 'BOOT_BOUNDARY'")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-di86-inputs-observer/observation.json')
report = json.loads(path.read_text())
report['parentObserverSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Read-only first DI86 packet/command/callback observations; all125 PPC objects unchanged.',
    'Not an original DI86 response or physical-drive execution.']
path.write_text(json.dumps(report, indent=2) + '\n')

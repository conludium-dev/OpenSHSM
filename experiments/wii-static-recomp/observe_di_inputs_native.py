"""Read actual OS IPC-memory inputs and source initializer state at the retained DI boundary."""
from pathlib import Path
import ast
import hashlib
import json

parent = Path('experiments/wii-static-recomp/observe_es_vector_boot.py')
body = parent.read_text().replace('mass-es-open-boot', 'mass-sysconf-complete-boot').replace(
    'mass-es-vector-observer', 'mass-di-inputs-observer').replace('audit_es_open_boot.py', 'audit_sysconf_complete_boot.py')
node = next(node for node in ast.parse(body).body if isinstance(node, ast.Assign) and
    any(isinstance(target, ast.Name) and target.id == 'observer' for target in node.targets))
observer = r'''        if (context.pc == 0x80241c30 && context.lr == 0x80242384 && nwii::runtime::stmSubmitted == 28) {
            std::cout << "DI_IPC_INPUTS" << std::hex;
            for (uint32_t address : {0x80528a38u, 0x8052ab10u, 0x8052afc4u, 0x8052afc8u, 0x8052afe4u,
                0x8052ac90u, 0x8052ac94u, 0x80528a98u}) {
                std::cout << ' ' << nwii::runtime::bat_memory_read32(context, address);
            }
            std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context, 0x8052afc0))
                << ' ' << unsigned(nwii::runtime::bat_memory_read8(context, 0x8052ac85)) << std::dec << '\n';
        }
'''
literal = ast.get_source_segment(body, node.value)
body = body.replace(literal, repr(observer))
body = body.replace("env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}",
    "env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}\nenv['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'\nenv['SHSM_SC_LAB_FILE'] = '_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF'\nenv['SHSM_SC_LAB_PRODUCT'] = '_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt'")
body = body.replace("assert 'ES_VECTOR_CACHED 8053ff20 8' in result.stdout", "assert 'DI_IPC_INPUTS ' in result.stdout")
body = body.replace('pc=80212ff4 lr=80242fc8 msr=a032', 'pc=80241c30 lr=80242384 msr=2032').replace(
    "('ES_', 'BOOT_BOUNDARY'", "('DI_', 'BOOT_BOUNDARY'")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-di-inputs-observer/observation.json')
report = json.loads(path.read_text())
report['parentObserverSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Read-only native OS IPC memory inputs/initializer state; ALL125 objects/headers/backend unchanged.',
    'Not original DI OPEN/drive results or physical Wii bootstrap.']
path.write_text(json.dumps(report, indent=2) + '\n')

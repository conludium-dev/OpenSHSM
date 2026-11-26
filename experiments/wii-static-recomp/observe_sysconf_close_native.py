"""Capture prepared first file CLOSE without changing any native PPC object or permission."""
from pathlib import Path
import ast
import hashlib
import json

parent = Path('experiments/wii-static-recomp/observe_es_vector_boot.py')
body = parent.read_text().replace('mass-es-open-boot', 'mass-sysconf-read-boot').replace(
    'mass-es-vector-observer', 'mass-sysconf-close-observer').replace('audit_es_open_boot.py', 'audit_sysconf_read_boot.py')
node = next(node for node in ast.parse(body).body if isinstance(node, ast.Assign) and
    any(isinstance(target, ast.Name) and target.id == 'observer' for target in node.targets))
observer = r'''        if (context.pc == 0x80212ff4 && context.lr == 0x80242240 && context.msr == 0x32 && nwii::runtime::stmSubmitted == 20) {
            std::cout << "SC_CLOSE_ARGUMENTS" << std::hex;
            for (unsigned index : {1u, 3u, 4u, 29u, 31u}) { std::cout << ' ' << context.gpr[index]; }
            std::cout << std::dec << '\n';
            for (bool cached : {false, true}) {
                for (auto [label, physical, length] : {std::tuple<const char*, uint32_t, unsigned>{"PACKET", 0x135e0080, 64},
                    {"WORK", 0x135e1020, 320}, {"CONTROL", 0x4b3000, 400}}) {
                    std::cout << "SC_CLOSE_" << label << (cached ? "_CACHED" : "_PHYSICAL");
                    for (unsigned index = 0; index < length; ++index) {
                        std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context,
                            physical + index + (cached ? 0x80000000u : 0xc0000000u)));
                    }
                    std::cout << '\n';
                }
            }
        }
'''
literal = ast.get_source_segment(body, node.value)
assert body.count(literal) == 1
body = body.replace(literal, repr(observer))
body = body.replace("env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}",
    "env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}\nenv['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'\nenv['SHSM_SC_LAB_FILE'] = '_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF'")
body = body.replace("assert 'ES_VECTOR_CACHED 8053ff20 8' in result.stdout", "assert 'SC_CLOSE_PACKET_CACHED 0 0 0 2' in result.stdout")
body = body.replace('pc=80212ff4 lr=80242fc8 msr=a032', 'pc=80212ff4 lr=80242240 msr=32')
body = body.replace("('ES_', 'BOOT_BOUNDARY'", "('SC_CLOSE_', 'BOOT_BOUNDARY'")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-sysconf-close-observer/observation.json')
report = json.loads(path.read_text())
report['parentObserverSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Prepared first file CLOSE only; ALL125 PPC objects/backend/header permissions unchanged.',
    'No close submission/result, file descriptor reset, callback or SC completion supplied.']
path.write_text(json.dumps(report, indent=2) + '\n')

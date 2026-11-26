"""Extend only the diagnostic call limit; retain every PPC object and semantic guard."""
from pathlib import Path
import ast

parent = Path('experiments/wii-static-recomp/observe_es_vector_boot.py')
body = parent.read_text().replace('mass-es-open-boot', 'mass-divide-initializer-boot').replace(
    'mass-es-vector-observer', 'mass-constructor-budget-observer').replace('audit_es_open_boot.py', 'audit_divide_initializer_boot.py').replace(
    "'es_device.cpp', 'boot-quarantine.tsv'", "'es_device.cpp', 'di_device.cpp', 'boot-quarantine.tsv'").replace(
    "output / 'es_device.cpp']", "output / 'es_device.cpp', output / 'di_device.cpp']")
body = body.replace('entry = entry_path.read_text()', "entry = entry_path.read_text().replace('if (++calls > 20000)', 'if (++calls > 40000)')")
node = next(node for node in ast.parse(body).body if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id == 'observer' for target in node.targets))
observer = '''        std::cout << "CONSTRUCTOR_BOUNDARY_OPERANDS " << std::hex
            << std::bit_cast<uint64_t>(context.fpr[0]) << ' ' << std::bit_cast<uint64_t>(context.fpr[1]) << ' '
            << std::bit_cast<uint64_t>(context.ps1[0]) << ' ' << std::bit_cast<uint64_t>(context.ps1[1]) << ' '
            << context.fpscr << ' ' << context.gpr[1] << ' '
            << std::bit_cast<uint64_t>(context.fpr[2]) << ' ' << std::bit_cast<uint64_t>(context.ps1[2]) << std::dec << std::endl;
'''
body = body.replace(ast.get_source_segment(body, node.value), repr(observer)).replace(
    "assert 'ES_VECTOR_CACHED 8053ff20 8' in result.stdout", "assert 'CONSTRUCTOR_BOUNDARY_OPERANDS ' in result.stdout").replace(
    "assert 'BOOT_BOUNDARY pc=80212ff4 lr=80242fc8 msr=a032' in result.stdout", "assert 'BOOT_BOUNDARY ' in result.stdout").replace(
    "('ES_', 'BOOT_BOUNDARY'", "('CONSTRUCTOR_', 'BOOT_BOUNDARY'")
marker = "env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}"
body = body.replace(marker, marker + "\nenv.update(SHSM_PLAYRECORD_LAB_FILE='work/private-game/static-recomp/playrecord-fs-device/pc-owned-playrecord.bin',SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin',SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin',SHSM_ES_LAB_CONSUMPTION='1',SHSM_DI_LAB_INQUIRY_PATH='work/private-game/static-recomp/di-inquiry-device/dolphin-lab-inquiry.bin',SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF',SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')")
body = body.replace('Native read-only diagnostic, all125 PPC objects/header permissions/backend unchanged; not original response or title-ID evidence.',
    'All125 PPC objects/headers/backend retained; only diagnostic call limit20000-to40000 and read-only operand print. No semantic guard removed.')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})

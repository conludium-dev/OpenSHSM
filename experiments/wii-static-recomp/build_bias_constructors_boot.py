"""Lower all byte-checked, symbolically matched bias constructors in the existing module."""
from pathlib import Path
import ast
import json
from bias_constructor_lowering import select, lower

experiment = Path('experiments/wii-static-recomp')
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
sites = select(dol, 'work/private-game/static-recomp/dtk-output/asm')
base_path = Path('work/private-game/static-recomp/mass-fp-registration-boot')
previous = json.loads((base_path / 'build.json').read_text())
selected = {}
for row in previous['records']:
    text, changes = lower(Path(row['source']).read_text(), dol, sites)
    if changes:
        selected[row['file']] = (text, changes)
assert any(site['function'] == 0x80017480 for _, changes in selected.values() for site in changes)
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-fp-registration-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-bias-constructors-boot'").replace(
    "('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_fp_registration_boot.py',)").replace(
    "'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'di_device.cpp', 'boot-quarantine.tsv'")
start, end = body.index("packet = output / 'ipc_open_packet.h'"), body.index('records = [dict(row)')
body = body[:start] + '''
front = output / 'ipc_ack_frontend.h'
wrapper = output / 'boot-wrapper.cpp'
fs_source = runtime / 'src/hle/devices/fs_device.cpp'
''' + body[end:]
node = next(node for node in ast.parse(body).body if isinstance(node, ast.For)
    and isinstance(node.target, ast.Name) and node.target.id == 'name' and isinstance(node.iter, ast.Tuple)
    and any(isinstance(value, ast.Constant) and value.value == 'output_62.cpp' for value in node.iter.elts))
loop = ast.get_source_segment(body, node)
function = 'def compile_record(name):\n' + loop.split('\n', 1)[1]
function = function.replace("    source.write_bytes(Path(row['source']).read_bytes())", "    source.write_text(selected[name][0])")
function += "\n    print('BIAS_OBJECT ' + name, flush=True)\n\nimport concurrent.futures\nwith concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:\n    list(pool.map(compile_record, sorted(selected)))"
body = body.replace(loop, function)
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp', output / 'di_device.cpp'")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_BIAS_CONSTRUCTORS_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env.update(SHSM_PLAYRECORD_LAB_FILE='work/private-game/static-recomp/playrecord-fs-device/pc-owned-playrecord.bin',SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin',SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin',SHSM_ES_LAB_CONSUMPTION='1',SHSM_DI_LAB_INQUIRY_PATH='work/private-game/static-recomp/di-inquiry-device/dolphin-lab-inquiry.bin',SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF',SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')\n    result = subprocess.run([str(exe),")
namespace = {**globals(), '__file__': __file__}
exec(compile(body, str(parent), 'exec'), namespace)
sha = namespace['sha']
output = Path('work/private-game/static-recomp/mass-bias-constructors-boot')
report = json.loads((output / 'build.json').read_text())
report['loweringSha256'] = sha(experiment / 'bias_constructor_lowering.py')
report['sites'] = sites
report['changes'] = {name: changes for name, (_, changes) in selected.items()}
report['limits'] = ['Only constructor prefixes whose original byte/data flow yields measured signed-int4330 operands.',
    'Existing finite-family helper/operand/FP profile guards unchanged; no general fsubs support.',
    '91 static matches do not mean91 whole-function behavioral oracles or completed startup.',
    'Runtime continuation and all unchanged module contracts require fresh audit.']
(output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')

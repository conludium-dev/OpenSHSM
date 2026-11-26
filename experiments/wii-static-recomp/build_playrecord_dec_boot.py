"""Rebuild every object for the extended ClockContext ABI and execute actual mtdec."""
from pathlib import Path
import ast
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-playrecord-seek-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-playrecord-dec-boot'").replace(
    "('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_playrecord_seek_boot.py', 'verify_dec_clock_component.py', 'verify_playrecord_dec_dolphin.py')").replace(
    "'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'di_device.cpp', 'boot-quarantine.tsv'")
start,end = body.index("packet = output / 'ipc_open_packet.h'"),body.index('records = [dict(row)')
changes = '''
front = output / 'ipc_ack_frontend.h'
wrapper = output / 'boot-wrapper.cpp'
component = root / 'dec-clock-component'
prep = json.loads((component / 'preparation.json').read_text())
assert sha(component / 'timebase_adapter.h') == prep['headerHashes'][str(component / 'timebase_adapter.h')]
(output / 'timebase_adapter.h').write_bytes((component / 'timebase_adapter.h').read_bytes())
for name in ('dec_clock_adapter.h','playrecord_dec_adapter.h'):
    (output / name).write_bytes((experiment / name).read_bytes())
replace(front, '#include "playrecord_seek_dispatch.h"', '#include "playrecord_seek_dispatch.h"\\n#include "playrecord_dec_adapter.h"')
policy = output / 'boot-quarantine.tsv'
replace(policy, '802106E0\\tUNVERIFIED_PROCESSOR_REGISTER_22\\n', '')
fs_source = runtime / 'src/hle/devices/fs_device.cpp'
'''
body = body[:start] + changes + body[end:]
node = next(node for node in ast.parse(body).body if isinstance(node,ast.For) and
    isinstance(node.target,ast.Name) and node.target.id == 'name' and isinstance(node.iter,ast.Tuple) and
    any(isinstance(value,ast.Constant) and value.value == 'output_62.cpp' for value in node.iter.elts))
loop = ast.get_source_segment(body,node)
function = 'def compile_record(name):\n' + loop.split('\n',1)[1]
function = function.replace("    source.write_bytes(Path(row['source']).read_bytes())",
    "    source.write_bytes(Path(row['source']).read_bytes())\n    if name == 'output_63.cpp':\n        replace(source,'    ctx.write_dec(ctx.gpr[3]); // mtdec r3','    nwii::runtime::experiment_playrecord_dec_write(ctx,ctx.gpr[3]);')")
function += "\n    print('DEC_ABI_OBJECT ' + name,flush=True)\n\nimport concurrent.futures\nwith concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:\n    list(pool.map(compile_record,[row['file'] for row in records]))"
body = body.replace(loop,function)
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp', output / 'di_device.cpp'")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_PLAYRECORD_DEC_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env.update(SHSM_PLAYRECORD_LAB_FILE='work/private-game/static-recomp/playrecord-fs-device/pc-owned-playrecord.bin',SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin',SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin',SHSM_ES_LAB_CONSUMPTION='1',SHSM_DI_LAB_INQUIRY_PATH='work/private-game/static-recomp/di-inquiry-device/dolphin-lab-inquiry.bin',SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF',SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')\n    result = subprocess.run([str(exe),")
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
path = Path('work/private-game/static-recomp/mass-playrecord-dec-boot/build.json')
report = json.loads(path.read_text())
report['limits'] = ['All125 objects rebuilt for existing ClockContext ownership-field ABI extension.',
    'Only original positive play-record mtdec admitted; same timebase/counter storage/EventScheduler.',
    'Expiry latches pending, DEC exception delivery remains guarded; no skipped timer/callback.',
    'Actual original callback/free completion and next boundary require fresh audit.']
path.write_text(json.dumps(report,indent=2) + '\n')

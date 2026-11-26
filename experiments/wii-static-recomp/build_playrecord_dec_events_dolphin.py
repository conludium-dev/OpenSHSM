"""Observe original mtdec and return without bypassing the original SDK alarm."""
from pathlib import Path
import ast
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_playrecord_events_dolphin.py')
body = parent.read_text().replace('dolphin-playrecord-events','dolphin-playrecord-dec-events').replace(
    'run_playrecord_events_disc_dolphin.ps1','run_playrecord_dec_events_disc_dolphin.ps1')
node = next(node for node in ast.parse(body).body if isinstance(node,ast.Assign)
    and any(isinstance(target,ast.Name) and target.id == 'sites' for target in node.targets))
sites = ast.literal_eval(node.value) + [(8,0x802106e0,0x7c7603a6,'PPCMtdec_before_write'),
    (9,0x802106e4,0x4e800020,'PPCMtdec_before_return')]
body = body.replace(ast.get_source_segment(body,node.value),repr(sites))
marker = "exec(compile(body, str(parent), 'exec'), {'__file__': __file__})"
assert body.count(marker) == 1
body = body.replace(marker, "body = body.replace('Seven private','Nine private').replace('seven replay sites','nine replay sites')\n"
    "marker = '    for slot, source in [(36, 0x804b2b4c)'\n"
    "assert body.count(marker) == 1\n"
    "body = body.replace(marker, '    code.extend([0x7c1602a6, dform(36, 0, 11, 60)])\\n' + marker)\n" + marker)
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
path = Path('work/private-game/static-recomp/dolphin-playrecord-dec-events/generation.json')
report = json.loads(path.read_text())
report['decParentGeneratorSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['decCounterSlot'] = 60
report['limits'].append('Two added original instruction replay sites record DEC before mtdec and before original BLR; extra privileged DEC read at slot60. Not cycle equivalence or DEC exception-delivery proof.')
path.write_text(json.dumps(report,indent=2) + '\n')

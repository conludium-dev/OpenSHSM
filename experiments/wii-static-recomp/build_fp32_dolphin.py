"""Observe original single transfers, including the actual constructor load/store."""
from pathlib import Path
import ast
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_fp64_dolphin.py'
body = parent.read_text().replace('dolphin-fp64','dolphin-fp32').replace('run_fp64_dolphin.ps1','run_fp32_dolphin.ps1')
body = body.replace('320', '192')
values = [0,0x80000000,1,0x80000001,0x007fffff,0x00800000,0x3f800000,0xbf800000,
    0x7f7fffff,0xff7fffff,0x7f800000,0xff800000,0x7fc00001,0xffc00042,0x7f800001,0xff800042]
pairs = [(0x80006b20,0x80006b2c),(0x800068ec,0x800068fc),(0x8002228c,0x800982b4)]
for name, value in [('values',values),('pairs',pairs)]:
    node = next(node for node in ast.parse(body).body if isinstance(node,ast.Assign)
        and any(isinstance(target,ast.Name) and target.id == name for target in node.targets))
    body = body.replace(ast.get_source_segment(body,node.value),repr(value))
body = body.replace("struct.pack_into('>Q', constants, index * 32, value)","struct.pack_into('>I', constants, index * 32, value)")
body = body.replace("struct.pack_into('>Q', constants, index * 32 + 20, value)","struct.pack_into('>I', constants, index * 32 + 20, value)")
body = body.replace("Original six double-transfer forms", "Original four single-transfer forms")
body = body.replace('pointer(replacement, 30,', 'pointer(replacement, 26,').replace(
    'pointer(code, 30, 0)', 'pointer(code, 26, 0)').replace('spr(30, 9, True)', 'spr(26, 9, True)')
body = body.replace('double-transfer cases: six forms', 'single-transfer cases: four forms')
for load, store in pairs:
    assert load != store
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
path = Path('work/private-game/static-recomp/dolphin-fp32/generation.json')
report = json.loads(path.read_text())
report['parentGeneratorSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['scope'] = 'Original lfs/stfs/lfsx/stfsx and NI setter unchanged; includes constructor80006B20/80006B2C. Adjacent observer exits, synthetic inputs/register/cache fixtures.'
report['limits'] = ['No original update forms found or admitted; only measured four forms.',
    'Load/store pairs test raw single encodings, both PS lanes and FPSCR at NI0/NI1, not enclosing constructor/retail startup or physical Wii.']
path.write_text(json.dumps(report,indent=2) + '\n')

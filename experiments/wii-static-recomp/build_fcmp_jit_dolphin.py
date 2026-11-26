"""Use the same unchanged original instruction fixture with the independent JIT backend."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/build_fcmp_dolphin.py')
body = parent.read_text().replace('dolphin-fcmp','dolphin-fcmp-jit').replace(
    'run_fcmp_dolphin.ps1','run_fcmp_jit_dolphin.ps1')
assert body.count('observer = []') == 1
body = body.replace('observer = []',"code.extend([(63 << 26) | (30 << 21) | (583 << 1),dform(54,30,29,712)])\nobserver = []")
exec(compile(body,str(parent),'exec'),{'__file__':__file__})

"""Retain the original nineteen-instruction prefix through its new FP register form."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/build_fsubs_variant_dolphin.py')
body = parent.read_text().replace('dolphin-fsubs-variant', 'dolphin-fsubs-gpr').replace(
    'run_fsubs_variant_dolphin.ps1', 'run_fsubs_gpr_dolphin.ps1').replace(
    '0x800a8ed8', '0x8017ace8').replace('0x800a8f18', '0x8017ad34').replace(
    'ec401828', 'ec201028').replace("report['functionBytes'] = 64", "report['functionBytes'] = 76").replace(
    'first16', 'first19').replace('fsubs f2,f0,f3', 'fsubs f1,f0,f2').replace('adjacent next lfs', 'adjacent next add')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
